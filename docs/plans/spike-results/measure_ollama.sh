#!/usr/bin/env bash
# Measure TTFT + throughput + GPU memory for a single Ollama chat call.
# Usage: ./measure_ollama.sh <round_id> <prompt> <output_csv>
# Output line: round_id,ttft_s,tps,gpu_mem_mib,total_tokens,total_s

round_id="$1"
prompt="$2"
out_csv="$3"
model="${MODEL:-qwen2.5:7b}"

payload=$(jq -nc --arg m "$model" --arg p "$prompt" '{model:$m, messages:[{role:"user",content:$p}], stream:true, options:{num_predict:120,temperature:0.2}}')

start_ns=$(python -c "import time; print(int(time.time_ns()))")
first_token_ns=""
total_tokens=0
end_ns=""

while IFS= read -r line; do
  if [ -z "$first_token_ns" ]; then
    first_token_ns=$(python -c "import time; print(int(time.time_ns()))")
  fi
  done_flag=$(echo "$line" | jq -r '.done // false' 2>/dev/null)
  if [ "$done_flag" = "true" ]; then
    end_ns=$(python -c "import time; print(int(time.time_ns()))")
    eval_count=$(echo "$line" | jq -r '.eval_count // 0' 2>/dev/null)
    total_tokens="$eval_count"
    break
  fi
done < <(curl -sS -N -X POST http://localhost:11434/api/chat -H "Content-Type: application/json" -d "$payload")

ttft_s=$(python -c "print(round(($first_token_ns - $start_ns)/1e9, 3))")
total_s=$(python -c "print(round(($end_ns - $start_ns)/1e9, 3))")
tps=$(python -c "print(round($total_tokens/max($total_s,0.001), 2))")
gpu_mem=$(docker exec ck-ollama nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr -d ' \r\n')

echo "$round_id,$ttft_s,$tps,$gpu_mem,$total_tokens,$total_s" >> "$out_csv"
echo "round=$round_id ttft=${ttft_s}s tps=$tps gpu=${gpu_mem}MiB tokens=$total_tokens total=${total_s}s"

#!/usr/bin/env python3
"""One-shot: populate meta profile's config.yaml with Ollama + Groq fallback.

Background: /opt/data/profiles/meta/config.yaml shipped with model='' providers={},
which causes hermes runtime to fall through to openrouter default → 401 (no key).
Other profiles (missive, showcase) use the dict-form schema. This script aligns
meta to match, preserving all other settings.

Usage (inside container, after `docker cp` to /tmp/_patch_meta_profile.py):
  /opt/hermes/.venv/bin/python3 /tmp/_patch_meta_profile.py
"""
import yaml, shutil, os, sys

SRC = '/opt/data/profiles/meta/config.yaml'
BAK = SRC + '.bak.20260522'

if not os.path.exists(SRC):
    print(f'ERROR: {SRC} not found', file=sys.stderr)
    sys.exit(1)

if not os.path.exists(BAK):
    shutil.copy(SRC, BAK)
    print(f'BACKUP: {BAK}')

with open(SRC) as f:
    cfg = yaml.safe_load(f) or {}

cfg['model'] = {
    'provider': 'custom',
    'model': 'qwen2.5:7b-ctx64k',
    'base_url': 'http://ck-ollama:11434/v1',
    'api_key_env': 'OLLAMA_API_KEY',
    'context_length': 65536,
}
cfg['fallback_model'] = {
    'model': 'llama-3.1-8b-instant',
    'provider': 'custom',
    'base_url': 'https://api.groq.com/openai/v1',
    'api_key_env': 'GROQ_API_KEY',
    'context_length': 128000,
}
# Override Hermes auxiliary context-length check: qwen2.5:7b-ctx64k Ollama
# preset IS 64K but model metadata reports default 32K. Without override,
# hermes ValueError-aborts with "below the minimum 64,000 required".
cfg.setdefault('auxiliary', {})
cfg['auxiliary'].setdefault('compression', {})
cfg['auxiliary']['compression']['model'] = 'qwen2.5:7b-ctx64k'
cfg['auxiliary']['compression']['context_length'] = 65536

# Drop OLD-schema empty placeholders that conflict with dict form
for old in ('providers', 'fallback_providers', 'credential_pool_strategies'):
    cfg.pop(old, None)

with open(SRC, 'w') as f:
    yaml.safe_dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

print('NEW model:', cfg['model'])
print('NEW fallback_model:', cfg['fallback_model'])

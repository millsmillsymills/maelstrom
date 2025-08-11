#!/usr/bin/env python3
import os, re, subprocess, json, glob

def run(cmd, input_bytes=None):
    if input_bytes is not None and isinstance(input_bytes, bytes):
        cp = subprocess.run(cmd, input=input_bytes, capture_output=True)
        # decode for consistency
        cp.stdout = cp.stdout.decode(errors='ignore') if isinstance(cp.stdout, (bytes, bytearray)) else cp.stdout
        cp.stderr = cp.stderr.decode(errors='ignore') if isinstance(cp.stderr, (bytes, bytearray)) else cp.stderr
        return cp.returncode, cp.stdout, cp.stderr
    cp = subprocess.run(cmd, input=input_bytes, capture_output=True, text=True)
    return cp.returncode, cp.stdout, cp.stderr

def get_owner_repo():
    rc, out, _ = run(['bash','-lc','git remote get-url origin 2>/dev/null'])
    m = re.search(r'github.com[:/]+([^/]+/[^/.]+)', out.strip())
    return m.group(1) if m else ''

def gh_post(url: str, obj: dict):
    payload = json.dumps(obj).encode()
    cmd = [ 'bash','-lc', f"./scripts/github_api.sh -X POST '{url}' --data @-" ]
    rc, out, err = run(cmd, input_bytes=payload)
    if rc != 0:
        print('WARN: POST failed', url, err)
        return {}
    try:
        return json.loads(out)
    except Exception:
        return {}

def main():
    owner_repo = get_owner_repo()
    if not owner_repo:
        print('No origin repo found; aborting')
        return
    files = sorted(glob.glob('/home/mills/tools/duo/logs/resurgent_code_focus_*.md'))
    if not files:
        print('No focused scan MD found; aborting')
        return
    path = files[-1]
    text = open(path).read().splitlines()
    issues = []
    cur = None
    data = {}
    for ln in text:
        m = re.match(r'^###\s+(\S.*)$', ln)
        if m:
            cur = m.group(1).strip()
            data[cur] = { 'missing': [] }
            continue
        if cur:
            if 'missing' in ln.lower():
                # e.g., "- README: missing"
                data[cur]['missing'].append(ln.strip('- ').strip())
    # Create issues for projects with missing items
    for proj, d in data.items():
        missing = [m for m in d['missing'] if 'missing' in m.lower()]
        if not missing:
            continue
        title = f"Hygiene: {proj} — add/normalize: " + ', '.join(sorted(set([m.split(':',1)[0] for m in missing])))
        body_lines = [f"Source: {path}", '', f"## Missing items for {proj}"]
        for m in missing:
            body_lines.append(f"- [ ] {m}")
        body_lines += ['', '## Suggested next steps',
                       '- Add a minimal README with purpose, setup, and status.',
                       '- Add tests/CI if repo contains living code.',
                       '- If this is a sandbox or archive, mark it clearly to avoid confusion.']
        issue = gh_post(f'https://api.github.com/repos/{owner_repo}/issues',
                        { 'title': title, 'body': '\n'.join(body_lines), 'labels': ['ops','hygiene'] })
        if issue.get('html_url'):
            print('ISSUE', issue['html_url'])
        else:
            print('WARN: issue not created for', proj)

if __name__ == '__main__':
    main()

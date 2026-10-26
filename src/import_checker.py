"""Multi-language import extraction and resolution (v4)."""
import re, posixpath, json

EXT_LANG = {}
for e in ('.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.mts', '.cts', '.vue', '.svelte'): EXT_LANG[e] = 'js'
for e in ('.py', '.pyi'): EXT_LANG[e] = 'py'
EXT_LANG['.go'] = 'go'
for e in ('.java', '.kt', '.kts', '.scala', '.groovy'): EXT_LANG[e] = 'jvm'
EXT_LANG['.cs'] = 'cs'
EXT_LANG['.rs'] = 'rs'
EXT_LANG['.php'] = 'php'
EXT_LANG['.rb'] = 'rb'
for e in ('.c', '.cc', '.cpp', '.cxx', '.h', '.hh', '.hpp', '.hxx', '.m', '.mm'): EXT_LANG[e] = 'c'
EXT_LANG['.swift'] = 'swift'
EXT_LANG['.dart'] = 'dart'
CODE_GLOBS = ['*' + e for e in EXT_LANG]


def lang_of(path):
    i = path.rfind('.')
    return EXT_LANG.get(path[i:].lower()) if i >= 0 else None


TESTRE = re.compile(
    r"(^|/)(tests?|__tests__|__mocks__|spec|specs|e2e|fixtures?|testing|test-utils|testdata|stories|storybook|"
    r"benchmarks?|examples?|samples?|scripts?|docs?|vendor|third_party|thirdparty|external)(/|$)"
    r"|\.(test|spec|stories|bench)\.[a-z]+$|(^|/)test_[^/]*\.py$|_test\.(py|go)$|conftest\.py$"
    r"|(^|/)src/test/|(Test|Tests|Spec|IT)\.(java|kt|scala|cs|swift)$|\.Tests?(/|\.)|_spec\.rb$|_test\.dart$", re.I)

JS_PATS = [re.compile(r"""^\s*import\s+(type\s+)?(?P<names>[^'"]*?)\s*from\s*['"](?P<spec>[^'"]+)['"]"""),
           re.compile(r"""^\s*import\s*['"](?P<spec>[^'"]+)['"]"""),
           re.compile(r"""^\s*export\s+(type\s+)?(?P<names>[^'"]*?)\s*from\s*['"](?P<spec>[^'"]+)['"]"""),
           re.compile(r"""^\s*\}?\s*(?P<names>[^'"]*?)\}?\s*from\s*['"](?P<spec>[^'"]+)['"]\s*;?\s*$"""),
           re.compile(r"""require\(\s*['"](?P<spec>[^'"]+)['"]\s*\)"""),
           re.compile(r"""import\(\s*['"](?P<spec>[^'"]+)['"]\s*\)""")]
PY_FROM = re.compile(r"^\s*from\s+(?P<spec>\.*[\w.]*)\s+import\s+(?P<names>.+)$")
PY_IMP = re.compile(r"^\s*import\s+(?P<mods>[\w., ]+?)(\s+as\s+\w+)?\s*(#.*)?$")
GO_IMP = re.compile(r'^\s*(import\s+)?(\(\s*)?(?P<alias>[\w.]+\s+)?"(?P<spec>[\w.\-~/]+)"\s*\)?\s*(//.*)?$')
JVM_IMP = re.compile(r"^\s*import\s+(static\s+)?(?P<spec>[\w.]+?)(\.\*|\._|\.\{[^}]*\})?\s*;?\s*(//.*)?$")
CS_USING = re.compile(r"^\s*(global\s+)?using\s+(static\s+)?(\w+\s*=\s*)?(?P<spec>[A-Za-z_][\w.]*)\s*;")
RS_USE = re.compile(r"^\s*(pub(\([^)]*\))?\s+)?use\s+(?P<spec>[\w:]+)(::\{(?P<names>[^}]*)\}|::\*)?")
RS_EXTERN = re.compile(r"^\s*extern\s+crate\s+(?P<spec>\w+)")
PHP_USE = re.compile(r"^\s*use\s+(function\s+|const\s+)?\\?(?P<spec>[A-Za-z_][\w\\]*)")
PHP_REQ = re.compile(r"""^\s*(require|include)(_once)?\s*\(?\s*(__DIR__\s*\.\s*)?['"](?P<spec>[^'"]+)['"]""")
RB_REQ = re.compile(r"""^\s*(?P<kind>require|require_relative|load)\s*\(?\s*['"](?P<spec>[^'"]+)['"]""")
C_INC = re.compile(r"""^\s*#\s*(include|import)\s*(?P<q>["<])(?P<spec>[^">]+)[">]""")
SWIFT_IMP = re.compile(r"^\s*(@testable\s+|@_exported\s+)?import\s+(class\s+|struct\s+|enum\s+|func\s+|protocol\s+)?(?P<spec>[\w.]+)\s*$")
DART_IMP = re.compile(r"""^\s*(import|export)\s+['"](?P<spec>[^'"]+)['"]""")

GREP_RE = (r"^\s*(import|from|export|using|global using|use|pub use|extern crate|require|require_relative|load|include|"
           r"require_once|include_once|#\s*include|#\s*import|@testable)\b|require\(|import\(|^\s*(\(\s*)?([\w.]+\s+)?\"[\w.~/-]+\"\s*\)?\s*$")


def parse(line, lang):
    """-> list of (spec, names:set, typeonly:bool, kind)"""
    out = []
    s = line.strip()
    if not s or s.startswith(('//', '/*', '*')) and lang not in ('py', 'rb'):
        return out
    if lang == 'js':
        for i, p in enumerate(JS_PATS):
            for m in p.finditer(line):
                g = m.groupdict()
                names = set(re.findall(r"[A-Za-z_$][\w$]*", g.get('names') or '')) - {'type', 'as', 'from', 'import', 'export', 'default'}
                out.append((g['spec'], names, bool(re.match(r"^\s*(import|export)\s+type\b", line)), ''))
            if out and i < 4: break
    elif lang == 'py':
        m = PY_FROM.match(line)
        if m:
            out.append((m.group('spec'), set(re.findall(r"\w+", m.group('names').split('#')[0])) - {'as'}, False, ''))
        else:
            m = PY_IMP.match(line)
            if m:
                for mod in m.group('mods').split(','):
                    mod = mod.strip().split(' ')[0]
                    if mod: out.append((mod, set(), False, ''))
    elif lang == 'go':
        m = GO_IMP.match(line)
        if m and ('/' in m.group('spec') or '.' in m.group('spec') or m.group(1)):
            out.append((m.group('spec'), set(), False, ''))
    elif lang == 'jvm':
        m = JVM_IMP.match(line)
        if m: out.append((m.group('spec'), set(), False, ''))
    elif lang == 'cs':
        m = CS_USING.match(line)
        if m and not re.match(r"^\s*using\s*\(", line): out.append((m.group('spec'), set(), False, ''))
    elif lang == 'rs':
        m = RS_USE.match(line) or RS_EXTERN.match(line)
        if m:
            names = set(re.findall(r"\w+", (m.groupdict().get('names') or '')))
            out.append((m.group('spec').rstrip(':'), names, False, ''))
    elif lang == 'php':
        m = PHP_USE.match(line)
        if m and not re.match(r"^\s*use\s+\w+\s*;?\s*$", line) or (m and '\\' in m.group('spec')):
            out.append((m.group('spec'), set(), False, 'ns'))
        else:
            m = PHP_REQ.match(line)
            if m: out.append((m.group('spec'), set(), False, 'file'))
    elif lang == 'rb':
        m = RB_REQ.match(line)
        if m: out.append((m.group('spec'), set(), False, m.group('kind')))
    elif lang == 'c':
        m = C_INC.match(line)
        if m: out.append((m.group('spec'), set(), False, m.group('q')))
    elif lang == 'swift':
        m = SWIFT_IMP.match(line)
        if m: out.append((m.group('spec'), set(), False, ''))
    elif lang == 'dart':
        m = DART_IMP.match(line)
        if m: out.append((m.group('spec'), set(), False, ''))
    seen = set(); res = []
    for o in out:
        if o[0] not in seen:
            seen.add(o[0]); res.append(o)
    return res


def strip_json(t):
    t = re.sub(r"(?<!:)//[^\n]*", "", t); t = re.sub(r"/\*.*?\*/", "", t, flags=re.S); return re.sub(r",(\s*[}\]])", r"\1", t)


class Resolver:
    """Built from the file list at a commit plus a few manifest files (read via show(path))."""

    def __init__(self, paths, show):
        self.paths = set(paths)
        self.dirs = set()
        for p in paths:
            parts = p.split('/')
            for k in range(1, len(parts)):
                self.dirs.add('/'.join(parts[:k]))
        # suffix index: 'a/b/c' -> shortest full path ending with it (dirs and files without ext)
        self.suf = {}
        for p in sorted(self.paths | self.dirs, key=len):
            q = p
            base = re.sub(r"\.[A-Za-z0-9]+$", "", q) if q in self.paths else q
            parts = base.split('/')
            for k in range(len(parts)):
                sfx = '/'.join(parts[k:])
                if sfx not in self.suf: self.suf[sfx] = base
        # dotted directory names (C# project folders like Foo.Bar.Core)
        self.dotdirs = {}
        for d in self.dirs:
            b = d.rsplit('/', 1)[-1]
            if '.' in b and b not in self.dotdirs: self.dotdirs[b] = d
        self.ts, self.pkg, self.gomod, self.cargo, self.psr4, self.pub = [], {}, [], {}, [], {}
        for p in self.paths:
            if 'node_modules' in p or '/vendor/' in p or p.count('/') > 6: continue
            b = p.rsplit('/', 1)[-1]; d = posixpath.dirname(p)
            try:
                if re.fullmatch(r"(tsconfig[\w.-]*|jsconfig)\.json", b):
                    co = json.loads(strip_json(show(p))).get('compilerOptions', {})
                    base = posixpath.normpath(posixpath.join(d, co.get('baseUrl', '.')))
                    al = {k.rstrip('*'): [posixpath.normpath(posixpath.join(base, x.rstrip('*'))) for x in v]
                          for k, v in (co.get('paths') or {}).items()}
                    if al: self.ts.append((d + '/' if d else '', al))
                elif b == 'package.json':
                    n = json.loads(show(p)).get('name')
                    if n: self.pkg[n] = d or '.'
                elif b == 'go.mod':
                    m = re.search(r"^module\s+(\S+)", show(p), re.M)
                    if m: self.gomod.append((d, m.group(1)))
                elif b == 'Cargo.toml':
                    t = show(p); m = re.search(r"\[package\][^\[]*?name\s*=\s*\"([^\"]+)\"", t, re.S)
                    if m: self.cargo[m.group(1).replace('-', '_')] = d
                elif b == 'composer.json':
                    j = json.loads(show(p))
                    for sec in ('autoload', 'autoload-dev'):
                        for ns, dirs in ((j.get(sec) or {}).get('psr-4') or {}).items():
                            for x in (dirs if isinstance(dirs, list) else [dirs]):
                                self.psr4.append((ns.rstrip('\\'), posixpath.normpath(posixpath.join(d, x))))
                elif b == 'pubspec.yaml':
                    m = re.search(r"^name:\s*(\S+)", show(p), re.M)
                    if m: self.pub[m.group(1)] = d
            except Exception:
                pass
        self.ts.sort(key=lambda x: -len(x[0])); self.psr4.sort(key=lambda x: -len(x[0]))
        self.gomod.sort(key=lambda x: -len(x[1]))
        self.pyroots = [''] + sorted({p.split('/')[0] + '/' for p in self.paths if p.endswith('/__init__.py') and p.split('/')[0] in ('src', 'lib', 'python', 'packages', 'libs')})

    def exists(self, p):
        p = p.rstrip('/')
        if p in self.paths or p in self.dirs: return p
        for e in list(EXT_LANG) + ['/index.ts', '/index.js', '/__init__.py', '/mod.rs']:
            if p + e in self.paths: return p
        return None

    def by_suffix(self, rel):
        rel = rel.strip('/')
        return self.suf.get(rel)

    def resolve(self, spec, file, lang, kind=''):
        fd = posixpath.dirname(file)
        if lang == 'js':
            if spec.startswith('.'): return posixpath.normpath(posixpath.join(fd, spec))
            for d, al in self.ts:
                if d and not file.startswith(d): continue
                for a, tg in al.items():
                    if a and spec.startswith(a):
                        return posixpath.normpath(tg[0] + '/' + spec[len(a):]) if tg else None
            best = None
            for n, d in self.pkg.items():
                if spec == n or spec.startswith(n + '/'):
                    if best is None or len(n) > len(best[0]): best = (n, d)
            if best:
                rest = spec[len(best[0]):].lstrip('/')
                return posixpath.normpath(posixpath.join(best[1], rest)) if rest else best[1]
            return None
        if lang == 'py':
            if spec.startswith('.'):
                lvl = len(spec) - len(spec.lstrip('.')); base = fd
                for _ in range(lvl - 1): base = posixpath.dirname(base)
                rest = spec.lstrip('.').replace('.', '/')
                return posixpath.normpath(posixpath.join(base, rest)) if rest else base
            rel = spec.replace('.', '/')
            for r in self.pyroots:
                if self.exists(r + rel) or self.exists(r + rel.split('/')[0]): return r + rel
            return self.by_suffix(rel) if '/' in rel else None
        if lang == 'go':
            for d, mod in self.gomod:
                if spec == mod or spec.startswith(mod + '/'):
                    rest = spec[len(mod):].lstrip('/')
                    return posixpath.normpath(posixpath.join(d, rest)) if rest else (d or '.')
            return None
        if lang in ('jvm', 'cs'):
            parts = spec.split('.')
            if lang == 'cs':
                for k in range(len(parts), 0, -1):
                    head = '.'.join(parts[:k])
                    if head in self.dotdirs:
                        return posixpath.join(self.dotdirs[head], *parts[k:]) if parts[k:] else self.dotdirs[head]
            for k in (len(parts), len(parts) - 1):
                if k >= 3:
                    hit = self.by_suffix('/'.join(parts[:k]))
                    if hit: return hit
            return None
        if lang == 'rs':
            parts = [p for p in spec.split('::') if p]
            if not parts: return None
            if parts[0] in ('crate', 'self', 'super'):
                root = fd
                while root and not (root + '/Cargo.toml' in self.paths): root = posixpath.dirname(root)
                if parts[0] == 'crate':
                    base = posixpath.join(root, 'src') if root else 'src'
                elif parts[0] == 'self':
                    base = fd
                else:
                    base = posixpath.dirname(fd)
                sub = parts[1:]
            elif parts[0] in self.cargo:
                base = posixpath.join(self.cargo[parts[0]], 'src'); sub = parts[1:]
            else:
                return None
            cur = base
            for i in range(len(sub), -1, -1):
                cand = posixpath.normpath(posixpath.join(base, *sub[:i])) if sub[:i] else base
                if self.exists(cand): return cand
            return cur
        if lang == 'php':
            if kind == 'file':
                return posixpath.normpath(posixpath.join(fd, spec)) if not spec.startswith('/') else spec.lstrip('/')
            for ns, d in self.psr4:
                if spec == ns or spec.startswith(ns + '\\'):
                    rest = spec[len(ns):].strip('\\').replace('\\', '/')
                    return posixpath.normpath(posixpath.join(d, rest)) if rest else d
            return self.by_suffix(spec.replace('\\', '/'))
        if lang == 'rb':
            if kind == 'require_relative': return posixpath.normpath(posixpath.join(fd, spec))
            return self.by_suffix(spec) if '/' in spec else (self.exists('lib/' + spec) and 'lib/' + spec)
        if lang == 'c':
            if kind == '"':
                cand = posixpath.normpath(posixpath.join(fd, spec))
                if cand in self.paths: return re.sub(r"\.[A-Za-z0-9]+$", "", cand)
            if '/' not in spec and kind != '"': return None
            hit = self.by_suffix(re.sub(r"\.[A-Za-z0-9]+$", "", spec))
            return hit
        if lang == 'swift':
            for d in (f'Sources/{spec}', spec):
                if d in self.dirs: return d
            return self.by_suffix(spec)
        if lang == 'dart':
            if spec.startswith('package:'):
                n, _, rest = spec[8:].partition('/')
                if n in self.pub: return posixpath.normpath(posixpath.join(self.pub[n] or '.', 'lib', rest))
                return None
            if spec.startswith('dart:'): return None
            return posixpath.normpath(posixpath.join(fd, spec))
        return None


def under(path, prefixes):
    if path is None: return False
    for p in prefixes:
        if p == '*': return True
        if '*' in p:
            rx = '^' + re.escape(p).replace(r'\*\*/', '(.*/)?').replace(r'\*\*', '.*').replace(r'\*', '[^/]*') + '$'
            if re.match(rx, path) or re.match(rx, path + '.ts'): return True
            continue
        q = p.rstrip('/')
        m = re.search(r"(\.[A-Za-z0-9]+)$", q)
        stem = q[:-len(m.group(1))] if (m and m.group(1).lower() in EXT_LANG) else q
        if path == q or path.startswith(q + '/') or path == stem or (stem != q and path.startswith(stem + '.')): return True
    return False


def ext_match(spec, names, t):
    mod, nm = t, ''
    if '::' in t:
        head, _, tail = t.rpartition('::')
        if '/' in head or head.startswith('@') or head.startswith('electron'):
            mod, nm = head, tail
    def norm(x):
        return x if x.startswith(('@', '.')) else x.replace('::', '.').replace('\\', '.').replace('/', '.')
    if mod.endswith(('/', '-', ':', '.', '\\')):
        ok = spec.startswith(mod) or norm(spec).startswith(norm(mod).rstrip('.') + '.') or norm(spec).startswith(norm(mod))
    else:
        ok = (spec == mod or spec.startswith(mod + '/') or spec.startswith(mod + '.') or spec.startswith(mod + '::')
              or spec.startswith(mod + '\\') or norm(spec) == norm(mod) or norm(spec).startswith(norm(mod) + '.'))
    if ok and re.fullmatch(r'/v\d+(/.*)?', spec[len(mod):] or 'x'):
        ok = False  # Go major-version path (e.g. math/rand/v2) is a different module
    if ok and nm:
        ok = nm in names or spec.endswith('.' + nm) or spec.endswith('::' + nm)
    return ok

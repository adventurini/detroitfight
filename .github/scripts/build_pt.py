"""Build the Brazilian Portuguese pages in /pt from their English twins.

usage: python3 .github/scripts/build_pt.py [--check] [--list page.html]

This is a helper, not a deploy step. Vercel still serves plain files: the pages in
/pt are committed like every other page. Run this after changing an English page
that has a Portuguese twin, then commit both.

How it works:
1. Each English page in PAGES is split into its visible strings (text, alt text,
   aria labels, placeholders, meta descriptions and the prose inside JSON-LD).
2. Each string is looked up in .github/i18n/pt.json (English string -> Portuguese).
   Inline tags inside a string show as {1}...{/1}, a line break as {br}.
3. Links to pages that have a twin are pointed at /pt/..., the head gets the
   Portuguese canonical and locale, and the trial form gets its Portuguese script.

A string with no entry in pt.json stops the build and is printed, so an English
edit can never silently leave English text on a Portuguese page. Add the missing
entry to pt.json and run again. Never edit a file in /pt by hand: the next build
overwrites it.

--check   build in memory and fail if any /pt file on disk would change
--list    print the strings of one English page (to see what needs translating)
"""
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STRINGS = os.path.join(ROOT, ".github", "i18n", "pt.json")
SITE = "https://detroitfight.com"

# English pages that have a Portuguese twin. Add a page here when it is translated.
PAGES = [
    "index.html", "jiu-jitsu.html", "kids.html", "schedule.html", "free-trial.html", "pricing.html",
    "boxing.html", "muay-thai.html", "mma.html", "martial-arts.html", "coaches.html",
    "coaches/sean-goolsby.html", "coaches/paulo-games.html", "the-gym.html", "private-lessons.html",
    "homeschool.html", "competition-team.html",
    "jiu-jitsu-oviedo.html", "jiu-jitsu-casselberry.html", "jiu-jitsu-winter-park.html", "muay-thai-oviedo.html",
    "mma-oviedo.html", "jiu-jitsu-near-ucf.html", "beginners-jiu-jitsu.html", "no-gi-jiu-jitsu.html",
    "self-defense.html", "guides/gi-vs-no-gi.html", "guides/bjj-vs-karate-taekwondo-kids.html",
    "guides/step-up-homeschool-jiu-jitsu.html", "privacy-policy.html", "terms.html",
]

TOKEN_RE = re.compile(r"(<!--.*?-->|<script\b.*?</script>|<style\b.*?</style>|<svg\b.*?</svg>|<[^>]+>)", re.S | re.I)
INLINE = {"a", "strong", "em", "b", "i", "span", "br", "small", "sup", "sub", "u", "abbr", "wbr"}
VOID = {"br", "wbr"}
META_KEYS = ("description", "og:title", "og:description", "og:image:alt", "twitter:title", "twitter:description", "twitter:image:alt")
LD_KEYS = {"text", "description", "disambiguatingDescription", "headline", "name", "caption"}
PATH_ATTRS = ("src", "href", "poster", "data-loop", "data-full")


def path_of(page):
    """index.html -> "/", jiu-jitsu.html -> "/jiu-jitsu"."""
    return "/" if page == "index.html" else "/" + page[:-5]


def pt_path(en_path):
    return "/pt" if en_path == "/" else "/pt" + en_path


TWINS = {path_of(p) for p in PAGES}


# ---------- splitting a page into strings ----------

def tagname(tok):
    m = re.match(r"<\s*(/?)\s*([a-zA-Z0-9]+)", tok)
    return (m.group(2).lower(), bool(m.group(1))) if m else (None, False)


def is_tag(tok):
    return tok.startswith("<")


def is_inline(tok):
    return is_tag(tok) and not tok.startswith("<!--") and tagname(tok)[0] in INLINE


def has_letters(s):
    return bool(re.search(r"[A-Za-zÀ-ÿ]", re.sub(r"&[a-zA-Z#0-9]+;", " ", s)))


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def split_segments(tokens):
    """Runs of text and inline tags between block level tags."""
    i, n = 0, len(tokens)
    while i < n:
        if is_tag(tokens[i]) and not is_inline(tokens[i]):
            i += 1
            continue
        j = i
        while j < n and (not is_tag(tokens[j]) or is_inline(tokens[j])):
            j += 1
        yield i, j
        i = j


def core_range(tokens, a, b):
    """Trim whitespace and wrapping tags from both ends of a run."""
    def blank(t):
        return not is_tag(t) and t.strip() == ""

    changed = True
    while changed and a < b:
        changed = False
        while a < b and blank(tokens[a]):
            a += 1
            changed = True
        while a < b and blank(tokens[b - 1]):
            b -= 1
            changed = True
        if a >= b:
            break
        t = tokens[a]
        if is_tag(t):
            n, close = tagname(t)
            if close or n in VOID:
                a += 1
                changed = True
                continue
            depth, match = 0, None
            for k in range(a, b):
                if is_tag(tokens[k]):
                    nn, cc = tagname(tokens[k])
                    if nn == n:
                        depth += -1 if cc else 1
                        if depth == 0:
                            match = k
                            break
            if match is None:
                a += 1
                changed = True
                continue
            if match == b - 1:
                a += 1
                b -= 1
                changed = True
                continue
        t = tokens[b - 1]
        if a < b and is_tag(t):
            n, close = tagname(t)
            if not close or n in VOID:
                b -= 1
                changed = True
                continue
            depth, match = 0, None
            for k in range(b - 1, a - 1, -1):
                if is_tag(tokens[k]):
                    nn, cc = tagname(tokens[k])
                    if nn == n:
                        depth += 1 if cc else -1
                        if depth == 0:
                            match = k
                            break
            if match is None:
                b -= 1
                changed = True
                continue
    if a >= b or not any(not is_tag(t) and has_letters(t) for t in tokens[a:b]):
        return None
    return a, b


def units_in(tokens, a, b):
    """Strings inside a run. A row of sibling links or buttons becomes one string each."""
    r = core_range(tokens, a, b)
    if not r:
        return
    a, b = r
    depth, top_text, spans, start = 0, False, [], None
    for k in range(a, b):
        t = tokens[k]
        if is_tag(t):
            n, close = tagname(t)
            if n in VOID:
                continue
            if close:
                depth -= 1
                if depth == 0 and start is not None:
                    spans.append((start + 1, k))
                    start = None
            else:
                if depth == 0:
                    start = k
                depth += 1
        elif depth == 0 and has_letters(t):
            top_text = True
    if top_text or not spans:
        yield a, b
    else:
        for x, y in spans:
            yield from units_in(tokens, x, y)


def to_key(tokens, a, b):
    """Tokens of one string -> (key with {1}{/1}{br} placeholders, the tags they stand for)."""
    out, tags, stack, num = [], {}, [], 0
    for t in tokens[a:b]:
        if is_tag(t):
            n, close = tagname(t)
            if n in VOID:
                out.append("{%s}" % n)
                tags[n] = t
            elif close:
                k = stack.pop() if stack else 0
                out.append("{/%d}" % k)
                tags["/%d" % k] = t
            else:
                num += 1
                stack.append(num)
                out.append("{%d}" % num)
                tags["%d" % num] = t
        else:
            out.append(t)
    return norm("".join(out)), tags


def from_translation(key, tr, tags):
    want = sorted(re.findall(r"\{(/?\d+|br|wbr)\}", key))
    got = sorted(re.findall(r"\{(/?\d+|br|wbr)\}", tr))
    if want != got:
        raise SystemExit("placeholders differ\n  en: %s\n  pt: %s" % (key, tr))
    return re.sub(r"\{(/?\d+|br|wbr)\}", lambda m: tags[m.group(1)], tr)


# ---------- the Portuguese build ----------

class Build:
    def __init__(self, strings):
        self.strings = strings
        self.missing = []
        self.used = set()

    def tr(self, key, page, optional=False):
        key = norm(key)
        if key in self.strings:
            self.used.add(key)
            return self.strings[key]
        if not optional:
            self.missing.append((page, key))
        return None

    def tag(self, tok, page):
        """Translate attributes and point links at the Portuguese twins."""
        name, close = tagname(tok)
        if close or tok.startswith("<!--") or name in ("script", "style", "svg"):
            return tok

        def attr(m):
            v = m.group(3)
            if not has_letters(v):
                return m.group(0)
            t = self.tr(v, page)
            return m.group(0) if t is None else "%s=%s%s%s" % (m.group(1), m.group(2), t, m.group(2))

        tok = re.sub(r'\b(alt|aria-label|title|placeholder)=(")([^"]*)"', attr, tok)
        if name == "meta":
            k = re.search(r'\b(?:name|property)="([^"]+)"', tok)
            if k and k.group(1) in META_KEYS:
                tok = re.sub(r'\b(content)=(")([^"]*)"', attr, tok)
            if k and k.group(1) == "og:url":
                tok = re.sub(r'content="[^"]*"', 'content="%s%s"' % (SITE, pt_path(path_of(page))), tok)
            if k and k.group(1) == "og:locale":
                tok = tok.replace("en_US", "pt_BR")
        if name == "html":
            tok = tok.replace('lang="en"', 'lang="pt-BR"')
        if name == "link" and 'rel="canonical"' in tok:
            tok = re.sub(r'href="[^"]*"', 'href="%s%s"' % (SITE, pt_path(path_of(page))), tok)
        if name == "link" and "hreflang" in tok:
            return tok

        def link(m):
            a, v = m.group(1), m.group(2)
            if re.match(r"(/|https?:|#|mailto:|tel:|sms:|data:)", v):
                if a == "href" and name == "a" and v.startswith("/") and "data-lang-switch" not in tok:
                    path, rest = re.match(r"([^?#]*)(.*)", v).groups()
                    clean = path.rstrip("/") or "/"
                    if clean in TWINS:
                        return '%s="%s%s"' % (a, pt_path(clean), rest)
                return m.group(0)
            return '%s="/%s"' % (a, v)  # a relative asset path breaks one folder down

        return re.sub(r'\b(%s)="([^"]*)"' % "|".join(PATH_ATTRS), link, tok)

    def ld(self, tok, page):
        m = re.match(r'(<script type="application/ld\+json">)(.*)(</script>)', tok, re.S)
        data = json.loads(m.group(2))

        def walk(o, parent_type=None):
            if isinstance(o, dict):
                typ = o.get("@type", parent_type)
                for k, v in list(o.items()):
                    if isinstance(v, str):
                        if k in LD_KEYS and has_letters(v):
                            t = self.tr(v, page)
                            if t is not None:
                                o[k] = t
                        elif k == "item" and typ == "ListItem" and v.startswith(SITE):
                            p = v[len(SITE):].rstrip("/") or "/"
                            if p in TWINS:
                                o[k] = SITE + pt_path(p)
                    else:
                        walk(v, typ)
                if o.get("@type") in ("FAQPage", "Service", "Event", "VideoObject"):
                    o["inLanguage"] = "pt-BR"
            elif isinstance(o, list):
                for v in o:
                    walk(v, parent_type)

        walk(data)
        return m.group(1) + json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + m.group(3)

    def page(self, page):
        src = open(os.path.join(ROOT, page), encoding="utf-8").read()
        en, pt = path_of(page), pt_path(path_of(page))
        # The language switch points the other way on the Portuguese page.
        switch = '<a href="%s" hreflang="pt-BR" lang="pt-BR" data-lang-switch>Português</a>' % pt
        if src.count(switch) != 2:
            raise SystemExit("%s: expected the language switch twice (contact strip and menu)" % page)
        src = src.replace(switch, '<a href="%s" hreflang="en" lang="en" data-lang-switch>English</a>' % en)
        tokens = TOKEN_RE.split(src)
        for i, t in enumerate(tokens):
            if not is_tag(t):
                continue
            if t.startswith('<script type="application/ld+json">'):
                tokens[i] = self.ld(t, page)
            else:
                tokens[i] = self.tag(t, page)
        for a, b in list(split_segments(tokens)):
            for x, y in list(units_in(tokens, a, b)):
                key, tags = to_key(tokens, x, y)
                t = self.tr(key, page)
                if t is None:
                    continue
                lead = "" if is_tag(tokens[x]) else re.match(r"\s*", tokens[x]).group(0)
                trail = "" if is_tag(tokens[y - 1]) else re.search(r"\s*$", tokens[y - 1]).group(0)
                tokens[x] = lead + from_translation(key, t, tags) + trail
                for k in range(x + 1, y):
                    tokens[k] = ""
        out = "".join(tokens)
        for find, repl, count in SCRIPT_PATCHES.get(page, []) + SCRIPT_PATCHES["*"]:
            n = out.count(find)
            if count is None:
                if n == 0:
                    continue
            elif n != count:
                raise SystemExit("%s: script patch expected %d time(s), found %d:\n  %s" % (page, count, n, find[:120]))
            out = out.replace(find, repl)
        return out


def page_strings(page):
    src = open(os.path.join(ROOT, page), encoding="utf-8").read()
    tokens = TOKEN_RE.split(src)
    seen, out = set(), []

    def add(k):
        k = norm(k)
        if k and k not in seen:
            seen.add(k)
            out.append(k)

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, str):
                    if k in LD_KEYS and has_letters(v):
                        add(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    for a, b in split_segments(tokens):
        for x, y in units_in(tokens, a, b):
            add(to_key(tokens, x, y)[0])
    for t in tokens:
        if t.startswith('<script type="application/ld+json">'):
            walk(json.loads(re.match(r"<script[^>]*>(.*)</script>", t, re.S).group(1)))
        elif is_tag(t) and not re.match(r"<(!--|script|style|svg)", t, re.I):
            for m in re.finditer(r'\b(alt|aria-label|title|placeholder)="([^"]*)"', t):
                if has_letters(m.group(2)):
                    add(m.group(2))
            k = re.search(r'\b(?:name|property)="([^"]+)"', t)
            c = re.search(r'\bcontent="([^"]*)"', t)
            if t.lower().startswith("<meta") and k and c and k.group(1) in META_KEYS:
                add(c.group(1))
    return out


# ---------- script text that differs on the Portuguese pages ----------
# Each entry is (English text exactly as it stands in the page, Portuguese text, how many
# times it must be found). None means "replace if present". A changed English script
# stops the build here, which is the cue to update the entry.

PT_SLOT_LABEL = r"""// Portuguese label for the time picker and the on page confirmation. The payload keeps the English label.
function dfcSlotLabelPt(iso) {
  const d = new Date(iso);
  const en = {}; const pt = {};
  new Intl.DateTimeFormat('en-US', { timeZone: DFC_TZ, day: 'numeric', hour: 'numeric', minute: '2-digit' }).formatToParts(d).forEach(p => { en[p.type] = p.value; });
  new Intl.DateTimeFormat('pt-BR', { timeZone: DFC_TZ, weekday: 'short', month: 'short' }).formatToParts(d).forEach(p => { pt[p.type] = p.value.replace('.', ''); });
  const wd = pt.weekday.charAt(0).toUpperCase() + pt.weekday.slice(1);
  return wd + ', ' + en.day + ' de ' + pt.month + ' às ' + en.hour + ':' + en.minute + ' ' + en.dayPeriod;
}
function dfcEffectiveOption(form) {"""

SCRIPT_PATCHES = {
    "*": [
        ("alert('Thanks. We text or call within one business day to set your class time.');",
         "alert('Obrigado. Enviamos uma mensagem ou ligamos em até um dia útil para marcar o horário da sua aula.');", None),
        ("userPaused ? 'Play the preview' : 'Pause the preview'", "userPaused ? 'Reproduzir a prévia' : 'Pausar a prévia'", None),
    ],
    "free-trial.html": [
        # Payload: English class fields stay (HighLevel workflows and staff read them); Portuguese ones are added.
        ("  cls.line = youth && sFirst ? cls.label + ' for ' + sFirst : cls.label;\n  if (adultOpt) cls.line += '. Students 15 and older train in our adult classes';\n",
         "  cls.line = youth && sFirst ? cls.label + ' for ' + sFirst : cls.label;\n  if (adultOpt) cls.line += '. Students 15 and older train in our adult classes';\n"
         "  // Portuguese copies of the class fields, for the Portuguese texts in HighLevel.\n"
         "  const ptOpt = adultOpt || opt;\n"
         "  const clsPt = { label: ptOpt ? (adultOpt ? (opt.dataset.adultLabelPt || adultOpt.dataset.labelPt) : ptOpt.dataset.labelPt) || cls.label : '', schedule: ptOpt ? (ptOpt.dataset.schedulePt || cls.schedule) : '' };\n"
         "  clsPt.line = youth && sFirst ? clsPt.label + ' para ' + sFirst : clsPt.label;\n"
         "  if (adultOpt) clsPt.line += '. Alunos a partir de 15 anos treinam nas aulas de adultos';\n", 1),
        ("    program: opt ? opt.textContent.trim() : '',\n", "    program: opt ? (opt.dataset.label || opt.textContent.trim()) : '',\n", 1),
        ("    class_line: cls.line,\n",
         "    class_line: cls.line,\n    language: 'pt-BR',\n    class_label_pt: clsPt.label,\n    class_schedule_pt: clsPt.schedule,\n    class_line_pt: clsPt.line,\n", 1),
        ("fLabel.textContent = on ? 'Student first name *' : 'First Name *';", "fLabel.textContent = on ? 'Nome do aluno *' : 'Nome *';", 1),
        ("lLabel.textContent = on ? 'Student last name' : 'Last Name *';", "lLabel.textContent = on ? 'Sobrenome do aluno' : 'Sobrenome *';", 1),
        ("fname.placeholder = on ? 'Student first name' : 'First name';", "fname.placeholder = on ? 'Nome do aluno' : 'Nome';", 1),
        ("lname.placeholder = on ? 'Student last name' : 'Last name';", "lname.placeholder = on ? 'Sobrenome do aluno' : 'Sobrenome';", 1),
        ("function dfcEffectiveOption(form) {", PT_SLOT_LABEL, 1),
        ("'Request My Free Class' : 'Book My Free Class'", "'Pedir Minha Aula Grátis' : 'Agendar Minha Aula Grátis'", 2),
        ("'<option value=\"\" disabled selected>Loading class times...</option>'", "'<option value=\"\" disabled selected>Carregando os horários...</option>'", 1),
        ("'<option value=\"\" disabled selected>Pick a day and time</option>'", "'<option value=\"\" disabled selected>Escolha o dia e o horário</option>'", 1),
        ("slots.map(s => '<option value=\"' + s + '\">' + dfcSlotLabel(s) + '</option>')", "slots.map(s => '<option value=\"' + s + '\">' + dfcSlotLabelPt(s) + '</option>')", 1),
        ("'<option value=\"text\">None of these work, text me</option>'", "'<option value=\"text\">Nenhum desses serve, me mande uma mensagem</option>'", 1),
        ("      btn.textContent = 'Book My Free Class';\n", "      btn.textContent = 'Agendar Minha Aula Grátis';\n", 1),
        ("      btn.textContent = 'Request My Free Class';\n", "      btn.textContent = 'Pedir Minha Aula Grátis';\n", 1),
        ("submitBtn.textContent = 'Submitted ✓';", "submitBtn.textContent = 'Enviado ✓';", 1),
        ("submitBtn.textContent = 'Sending...';", "submitBtn.textContent = 'Enviando...';", 1),
        ("submitBtn.textContent = 'Booking your class...';", "submitBtn.textContent = 'Agendando sua aula...';", 1),
        ("style=\"text-align:center;\">You\\'re Booked.</h2>'", "style=\"text-align:center;\">Aula Agendada.</h2>'", 1),
        ("esc(payload.class_label) + (payload.student_first_name ? ' for ' + esc(payload.student_first_name) : '') + ', ' + esc(payload.class_time_label)",
         "esc(payload.class_label_pt) + (payload.student_first_name ? ' para ' + esc(payload.student_first_name) : '') + ', ' + esc(dfcSlotLabelPt(payload.class_time))", 1),
        ("'A confirmation text is on its way. Save time at the door: <a href=\"/waiver\" style=\"color:#7D9B76;\">sign your waiver now</a>' + (payload.student_first_name ? ' (a parent signs for a child)' : '') + '. ' +",
         "'A mensagem de confirmação já está a caminho. Ganhe tempo na chegada: <a href=\"/waiver\" style=\"color:#7D9B76;\">assine o termo de responsabilidade agora</a> (o formulário está em inglês)' + (payload.student_first_name ? ' (um dos pais assina pela criança)' : '') + '. ' +", 1),
        ("'Wear workout clothes and bring water. We are at ' + mapLink + '. Questions? Call <a href=\"tel:4076966969\" style=\"color:#7D9B76;\">(407) 696-6969</a>.' +",
         "'Venha com roupa de treino e traga água. Estamos em ' + mapLink + '. Dúvidas? Ligue para <a href=\"tel:4076966969\" style=\"color:#7D9B76;\">(407) 696-6969</a>.' +", 1),
        ("style=\"text-align:center;\">You\\'re In.</h2>'", "style=\"text-align:center;\">Pedido Recebido.</h2>'", 1),
        ("style=\"text-align:center;\">We text you shortly to set your class time.</p>'", "style=\"text-align:center;\">Em breve enviamos uma mensagem para marcar o horário da sua aula.</p>'", 1),
        ("'You can find us at ' + mapLink + ', or call us at ' +", "'Estamos em ' + mapLink + '. Se preferir, ligue para ' +", 1),
        ("alert(booked ? 'You are booked. A confirmation text is on its way.' : 'Thanks. We text you shortly to set your class time.');",
         "alert(booked ? 'Aula agendada. A mensagem de confirmação já está a caminho.' : 'Obrigado. Em breve enviamos uma mensagem para marcar o horário da sua aula.');", 1),
        ("alert('Something went wrong sending your request. Please call (407) 696-6969 or email sean@detroitfight.com so we can get you booked. Sorry for the trouble.');",
         "alert('Algo deu errado ao enviar seu pedido. Ligue para (407) 696-6969 ou escreva para sean@detroitfight.com e nós agendamos sua aula. Desculpe o transtorno.');", 1),
        # Portuguese class names and times on the class options (sent as class_label_pt and class_schedule_pt).
        ('data-label="Boxing" data-schedule=', 'data-label-pt="Boxe" data-schedule-pt="segunda a sexta às 10 AM, 5:30 PM e 6:45 PM, sábado às 10 AM" data-label="Boxing" data-schedule=', 1),
        ('data-label="Muay Thai" data-schedule=', 'data-label-pt="Muay Thai" data-schedule-pt="segunda e quarta às 7:30 PM" data-label="Muay Thai" data-schedule=', 1),
        ('data-label="MMA" data-schedule=', 'data-label-pt="MMA" data-schedule-pt="terça e quinta às 7:30 PM" data-label="MMA" data-schedule=', 1),
        ('data-label="Jiu-Jitsu (Gi)" data-schedule=', 'data-label-pt="Jiu-Jitsu (com kimono)" data-schedule-pt="segunda a sexta às 6 PM, segunda e quarta às 6 AM, sábado às 11 AM" data-label="Jiu-Jitsu (Gi)" data-schedule=', 1),
        ('data-label="Jiu-Jitsu (No Gi)" data-schedule=', 'data-label-pt="Jiu-Jitsu (sem kimono)" data-schedule-pt="segunda a sexta às 6 PM, segunda e quarta às 6 AM, sábado às 11 AM" data-label="Jiu-Jitsu (No Gi)" data-schedule=', 1),
        ('data-label="Kids Jiu-Jitsu" data-schedule=', 'data-label-pt="Jiu-Jitsu Infantil" data-adult-label-pt="Jiu-Jitsu" data-schedule-pt="segunda a sexta às 4:45 PM, sábado às 10 AM" data-label="Kids Jiu-Jitsu" data-schedule=', 1),
        ('data-label="Youth Boxing" data-schedule=', 'data-label-pt="Boxe Infantil" data-adult-label-pt="Boxe" data-schedule-pt="segunda, quarta e sexta às 4:30 PM" data-label="Youth Boxing" data-schedule=', 1),
        ('data-label="Homeschool PE" data-schedule=', 'data-label-pt="Educação Física Homeschool" data-schedule-pt="segunda a quinta, das 10 AM às 12 PM, a partir de 11 de janeiro" data-label="Homeschool PE" data-schedule=', 1),
        ('data-label="Not sure yet" data-schedule=', 'data-label-pt="Ainda não sei" data-schedule-pt="temos aulas todos os dias úteis e sábado de manhã, horários completos em detroitfight.com/pt/schedule" data-label="Not sure yet" data-schedule=', 1),
    ],
}


def main(argv):
    if "--list" in argv:
        for s in page_strings(argv[argv.index("--list") + 1]):
            print(s)
        return
    strings = json.load(open(STRINGS, encoding="utf-8"))
    build = Build(strings)
    outputs = {p: build.page(p) for p in PAGES}
    if build.missing:
        print("%d string(s) have no Portuguese entry in .github/i18n/pt.json:" % len(build.missing))
        for page, key in build.missing:
            print("  [%s] %s" % (page, key))
        sys.exit(1)
    changed = []
    os.makedirs(os.path.join(ROOT, "pt"), exist_ok=True)
    for page, text in outputs.items():
        dest = os.path.join(ROOT, "pt", page)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        old = open(dest, encoding="utf-8").read() if os.path.exists(dest) else None
        if old != text:
            changed.append("pt/" + page)
            if "--check" not in argv:
                open(dest, "w", encoding="utf-8", newline="").write(text)
    unused = sorted(set(strings) - build.used)
    if unused:
        print("%d entr%s in pt.json no longer match any English string (safe to delete):" % (len(unused), "y" if len(unused) == 1 else "ies"))
        for k in unused:
            print("  " + k[:100])
    if "--check" in argv and changed:
        print("out of date: " + ", ".join(changed))
        sys.exit(1)
    print("built %d page(s); %s" % (len(outputs), "changed: " + ", ".join(changed) if changed else "nothing changed"))


if __name__ == "__main__":
    main(sys.argv[1:])

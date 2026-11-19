# Class 10 — predictions (written before running anything)

The lab asks for a guess, committed before looking: does the stored `<script>`
comment **show as text**, **cause an error**, or **run** in alice's browser?

## Part 1 — stored XSS

- **Prediction: it RUNS. The alert box pops in alice's browser.**
- Reasoning: `dashboard.html` renders the comment as
  `<td>{% autoescape false %}{{ n.comment }}{% endautoescape %}</td>`. Jinja2 is safe
  by default and would turn `<` into `&lt;`; `autoescape false` switches that off for
  this one expression. The stored string is then written into the HTML response
  character for character, so the browser parses `<script>…</script>` as a element
  and executes it. The grade comment is AES-GCM encrypted at rest, but encryption
  protects the database, not the page: the app decrypts it and hands it to the
  template unchanged.
- Follow-up prediction: `curl` alone will show the literal `<script>` tag but will
  not prove execution — only a real browser does that. The reliable command-line
  proof is the **absence of `&lt;`** and the presence of a raw `<script>alert` in the
  HTML alice receives.

## Part 2/3 — after removing `{% autoescape false %}`

- **Prediction: the same comment becomes inert text; no alert.**
- Reasoning: with default autoescape on, `<` becomes `&lt;` and `>` becomes `&gt;`,
  so the browser sees characters, not a tag. The database value does not change, and
  the teacher does not have to re-post: the escaping happens on the way **out**, at
  render time.
- Follow-up prediction: the raw string `<script>alert('XSS by Eve')</script>` must
  disappear from the HTML, and `&lt;script&gt;alert('XSS by Eve')&lt;/script&gt;`
  must appear instead.

## Part 4 — a normal comment with `<` and `&`

- **Prediction: it still displays correctly ("score < 10 … & retry").**
- Reasoning: escaping only changes how characters are transported, not how they look:
  `&lt;` renders as `<` and `&amp;` renders as `&`. Autoescaping is not
  "comment mangling".
- Follow-up prediction: the teacher page (`teacher.html`) needs the same fix, because
  it has the identical `autoescape false` line; fixing only the student dashboard
  would leave the teacher's own view vulnerable.

> This file records the predictions with reasons, written before the experiment.
> The lab says to commit your own guess with your pair; add yours next to each part
> as you go.

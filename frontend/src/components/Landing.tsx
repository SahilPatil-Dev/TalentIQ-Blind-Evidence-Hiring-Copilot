/**
 * Landing.tsx — the public home page, shown at "/" to visitors who are not signed in.
 * Signed-in people see the dashboard instead (see app/page.tsx).
 *
 * It is plain markup styled by the `.lp-*` rules in globals.css (section 14). The hero
 * animation (blacked-out name, marker-pen evidence, score) is CSS only, and is skipped for
 * people who ask their device for less motion. All names and résumé text are fictional.
 */
import Link from "next/link";
import { Icon } from "./Icon";
import { Brand } from "./Sidebar";

export function Landing() {
  return (
    <div className="lp">
    <header className="lp-nav">
      <div className="lp-wrap lp-nav-in">
        <div className="lp-brand"><Brand /></div>
        <nav className="lp-links" aria-label="Sections">
          <a href="#how">How it works</a>
          <a href="#features">Features</a>
          <a href="#governance">Governance</a>
          <a href="#roles">Roles</a>
        </nav>
        <div className="lp-nav-cta">
          <Link href="/login" className="btn btn-ghost btn-sm">Sign in</Link>
          <Link href="/register" className="btn btn-primary btn-sm">Get started</Link>
        </div>
      </div>
    </header>

    <section className="lp-hero">
      <div className="lp-blob lp-blob-a"></div>
      <div className="lp-blob lp-blob-b"></div>
      <div className="lp-wrap lp-hero-in">
        <div className="lp-hero-copy">
          <span className="lp-eyebrow"><i className="live-dot"></i> Blind, evidence-led hiring</span>
          <h1>Hire on <span className="lp-hl">evidence</span>.<br />Names come <span className="lp-ink">later</span>.</h1>
          <p className="lp-lead">TalentIQ hides who a candidate is, quotes the proof in their résumé, and scores it with plain maths. Every decision stays with a person, with a reason on record.</p>
          <div className="lp-cta">
            <Link href="/register" className="btn btn-primary lp-btn-lg">Start screening <Icon name="arrowRight" size={18} /></Link>
            <a href="#how" className="btn btn-ghost lp-btn-lg">See how it works</a>
          </div>
          <ul className="lp-proof">
            <li><Icon name="check" size={16} /> Identity sealed before the AI reads a word</li>
            <li><Icon name="check" size={16} /> No quote, no points</li>
            <li><Icon name="check" size={16} /> Every reveal is logged</li>
          </ul>
        </div>

        <div className="lp-stage" aria-hidden="true">
          <div className="lp-resume">
            <div className="lp-resume-top">
              <span className="lp-avatar"></span>
              <div className="lp-who">
                <span className="lp-redact w70">Alex Example</span>
                <span className="lp-redact w50">alex@example.test</span>
              </div>
              <span className="lp-chip lp-chip-seal"><Icon name="lock" size={13} /> Sealed</span>
            </div>
            <p className="lp-text">Graduated from <span className="lp-redact inline">Westgate University</span>. <span className="lp-redact inline">She</span> led a small backend team.</p>
            <p className="lp-text"><span className="lp-quote q1">Built a Django REST API for internal tools.</span></p>
            <p className="lp-text"><span className="lp-quote q2">Developed AI agents with LangGraph and RAG.</span></p>
            <p className="lp-text lp-dim">Enjoys hiking and chess.</p>
          </div>
          <div className="lp-score">
            <div className="lp-ring"><span>87</span></div>
            <small>Score by Python</small>
          </div>
          <span className="lp-float lp-f1"><Icon name="eyeOff" size={14} /> Name sealed</span>
          <span className="lp-float lp-f2"><Icon name="check" size={14} /> Quote verified +40</span>
          <span className="lp-float lp-f3"><Icon name="check" size={14} /> Quote verified +35</span>
        </div>
      </div>
    </section>

    <section className="lp-strip">
      <div className="lp-wrap lp-strip-in">
        <div><strong>0</strong><span>identity details sent to the AI</span></div>
        <div><strong>100%</strong><span>of scored quotes checked word for word</span></div>
        <div><strong>144</strong><span>identity variants tested per fairness run</span></div>
        <div><strong>1</strong><span>human decision, always with a reason</span></div>
      </div>
    </section>

    <section className="lp-section" id="how">
      <div className="lp-wrap">
        <div className="lp-head"><span className="lp-kicker">How it works</span><h2>From résumé to ranked shortlist in four steps</h2></div>
        <ol className="lp-steps">
          <li><span className="lp-n">1</span><h3>Hide identity</h3><p>Name, email, phone, university and pronouns are removed and locked away, encrypted.</p></li>
          <li><span className="lp-n">2</span><h3>Find evidence</h3><p>The AI quotes the sentence that proves each skill on your rubric.</p></li>
          <li><span className="lp-n">3</span><h3>Verify quotes</h3><p>Python checks every quote exists in the résumé. Invented claims earn nothing.</p></li>
          <li><span className="lp-n">4</span><h3>You decide</h3><p>Python adds up the score. You shortlist or archive, and say why.</p></li>
        </ol>
      </div>
    </section>

    <section className="lp-section lp-tint" id="features">
      <div className="lp-wrap">
        <div className="lp-head"><span className="lp-kicker">Features</span><h2>Built so the proof does the talking</h2></div>
        <div className="lp-grid">
          <article className="lp-card"><span className="lp-ic"><Icon name="eyeOff" size={22} /></span><h3>Blind by default</h3><p>The AI only ever sees redacted text, so a name or a school cannot sway the result.</p></article>
          <article className="lp-card"><span className="lp-ic"><Icon name="file" size={22} /></span><h3>Quote or no points</h3><p>Each point links to an exact sentence. Weak or missing evidence is shown honestly.</p></article>
          <article className="lp-card"><span className="lp-ic"><Icon name="check" size={22} /></span><h3>Maths, not mood</h3><p>Scores are plain arithmetic, so the same résumé always gets the same score.</p></article>
          <article className="lp-card"><span className="lp-ic"><Icon name="users" size={22} /></span><h3>People decide</h3><p>Nothing is shortlisted or rejected automatically. Every decision needs a written reason.</p></article>
          <article className="lp-card"><span className="lp-ic"><Icon name="unlock" size={22} /></span><h3>Audited reveal</h3><p>Identity opens only after a shortlist, with a reason. Who, when and why are logged.</p></article>
          <article className="lp-card"><span className="lp-ic"><Icon name="scale" size={22} /></span><h3>Fairness tested</h3><p>Swap names, schools and pronouns on one résumé and prove the score does not move.</p></article>
        </div>
      </div>
    </section>

    <section className="lp-section">
      <div className="lp-wrap">
        <div className="lp-head"><span className="lp-kicker">The difference</span><h2>Usual screening vs TalentIQ</h2></div>
        <div className="lp-compare">
          <div className="lp-col lp-before">
            <h3>Usual screening</h3>
            <ul>
              <li>Name and school are the first thing you see</li>
              <li>Skim for keywords, remember the vibe</li>
              <li>Hard to explain why someone was passed over</li>
              <li>Candidate data kept forever</li>
            </ul>
          </div>
          <div className="lp-col lp-after">
            <h3>With TalentIQ</h3>
            <ul>
              <li>Identity sealed until a shortlist</li>
              <li>Each skill backed by a verified quote</li>
              <li>Every decision has a reason and an audit trail</li>
              <li>Retention limits delete data on schedule</li>
            </ul>
          </div>
        </div>
      </div>
    </section>

    <section className="lp-section lp-dark" id="governance">
      <div className="lp-wrap lp-gov">
        <div>
          <span className="lp-kicker lp-kicker-light">Governance</span>
          <h2>Trust you can check, not just claim</h2>
          <p className="lp-lead-light">Hiring data is sensitive. TalentIQ keeps a tamper-evident record of who did what, and deletes data when it should.</p>
          <ul className="lp-gov-list">
            <li><Icon name="list" size={18} /><span><b>Hash-chained audit log</b> with an integrity check and CSV export</span></li>
            <li><Icon name="clock" size={18} /><span><b>Retention rules</b>, automatic cleanup and legal hold</span></li>
            <li><Icon name="key" size={18} /><span><b>Managed encryption keys</b> you can rotate from the app</span></li>
            <li><Icon name="clipboard" size={18} /><span><b>Compliance review</b> of live controls and open to-dos</span></li>
          </ul>
        </div>
        <div className="lp-log" aria-hidden="true">
          <div className="lp-log-row"><code>application.shortlist</code><span>recruiter</span><em>a41f…9c2</em></div>
          <div className="lp-link"></div>
          <div className="lp-log-row hot"><code>identity.reveal</code><span>&ldquo;Book the interview&rdquo;</span><em>7be0…d15</em></div>
          <div className="lp-link"></div>
          <div className="lp-log-row"><code>key.rotate</code><span>admin</span><em>c9d3…41a</em></div>
          <div className="lp-link"></div>
          <div className="lp-log-row"><code>retention.run</code><span>12 deleted</span><em>52aa…e07</em></div>
        </div>
      </div>
    </section>

    <section className="lp-section" id="roles">
      <div className="lp-wrap">
        <div className="lp-head"><span className="lp-kicker">Roles</span><h2>The right access for each person</h2></div>
        <div className="lp-roles">
          <article><h3>Administrator</h3><p>Users, keys, retention and deletion.</p></article>
          <article><h3>Recruiter</h3><p>Create roles, upload résumés, decide, reveal.</p></article>
          <article><h3>Reviewer</h3><p>Read-only blind review of candidates.</p></article>
          <article><h3>Auditor</h3><p>Audit log, fairness and compliance. No candidate data.</p></article>
        </div>
      </div>
    </section>

    <section className="lp-final">
      <div className="lp-wrap lp-final-in">
        <h2>See the evidence before the name.</h2>
        <p>Create an account and try the sample role with fictional candidates.</p>
        <div className="lp-cta lp-cta-c">
          <Link href="/register" className="btn lp-btn-white lp-btn-lg">Create an account</Link>
          <Link href="/login" className="btn lp-btn-line lp-btn-lg">Sign in</Link>
        </div>
      </div>
    </section>

    <footer className="lp-foot">
      <div className="lp-wrap lp-foot-in">
        <div className="lp-brand"><Brand /></div>
        <p>A portfolio project. Demo résumés are fictional. Redaction is pattern-based and misses some details, and the compliance page is a checklist, not legal advice.</p>
      </div>
    </footer>
    </div>
  );
}

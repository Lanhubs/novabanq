# NovaBanq
### Pan-African money, one tag away.

**StacStart Hackathon Submission — 2026**

---

## Executive Summary

Sending money across an African border still costs more, takes longer, and demands more paperwork than sending it across the street. NovaBanq is a mobile-first, AI-powered payments platform that lets anyone in Nigeria, Ghana, Kenya, Senegal, Côte d'Ivoire, or South Africa send money to anyone else in those six countries — instantly, across five currencies, for a transparent 1% fee — by typing an `@tag` or, with our AI assistant Nova, simply typing what they mean: *"send 5000 to david.ng."* Underneath the simple surface is a real double-entry ledger, atomic multi-currency settlement, bank-grade KYC, and a GenAI layer that is architecturally incapable of inventing a number it hasn't verified against your actual account. This isn't a mockup of a payments app. It's a payments engine with a conversational front door.

---

## 1. Problem & Opportunity

**Africa is the most expensive place on Earth to move your own money.**

According to the World Bank's Remittance Prices Worldwide data, sending $200 within or into Sub-Saharan Africa cost an average of **8.4% in fees** as of Q1 2024 — well above the 6.4% global average, and nearly three times the United Nations' Sustainable Development Goal target of 3% by 2030. Specific corridors are worse: sending money from South Africa to Zimbabwe averaged **12.7%** in the same period. These aren't edge cases — they're everyday transactions that fund school fees, medical bills, and small businesses across the continent. Remittances reached **$92 billion** flowing into Sub-Saharan Africa in 2024 alone, and for 19 of Africa's 54 countries, that money represents more than 4% of national GDP.

**The cost isn't really about distance — it's about fragmentation.** Africa is 54 countries, each with its own currency, central bank, and regulatory regime. A transfer from Lagos to Accra crosses as many institutional boundaries as a transfer from Lagos to London, but with none of the interoperable infrastructure that makes the latter cheap. Traditional banks route cross-border transfers through multiple correspondent intermediaries, each taking a cut and adding delay. Only **55% of African countries** currently permit electronic KYC, forcing people to repeat identity verification paperwork every time they cross a financial border — pushing many transactions into informal, cash-based channels that are cheaper but riskier and untraceable.

**The opportunity is that the underlying rails are finally being built — but the consumer experience hasn't caught up.** Africa's instant payment transaction volume grew from $775.7 billion in 2020 to nearly **$2 trillion in 2024**. Mobile money already carries 30% of the continent's cross-border transfers, at a fraction of bank fees. Continent-level infrastructure like the Pan-African Payment and Settlement System is coming online to let banks settle in local currencies directly. Analysts project Africa's cross-border payments market will nearly triple, from roughly $329 billion in 2025 to **$1 trillion by 2035**. The pipes are being laid. What's missing is a product that makes those pipes feel as easy to use as sending a text message — for the ordinary person, not just the bank.

That's the gap NovaBanq fills.

---

## 2. Innovative Solution

NovaBanq is a pan-African digital wallet and transfer platform built around one idea: **paying a person should feel like messaging them, not like filling out a wire form.**

### The building blocks

**@tag identity, not account numbers.** Every user gets a human-readable tag like `david.ng`. Sending money means typing a tag, not hunting for a bank name, account number, and routing code in a country whose banking conventions you don't know.

**Transparent pricing, every single time.** Before a transfer is confirmed, NovaBanq shows the exact fee, the exact exchange rate, and the exact amount the recipient will receive — in their currency, not an estimate. No hidden markups buried in the exchange rate, which is how many traditional providers quietly inflate their true cost.

**A real double-entry ledger — not a spreadsheet with a nice UI.** Every transfer is committed as a single atomic transaction across up to five ledger legs: debiting the sender, converting through a currency bridge at the live rate, crediting the recipient in their own currency, and collecting the fee — all or nothing. A transfer can never partially complete and leave money in limbo.

**Idempotency by design.** Every money-moving request carries a client-generated key. If a network call fails and the app retries, NovaBanq guarantees the transfer settles exactly once — never a double charge, regardless of how many times a request is retried.

**Bank-grade onboarding before a single unit of currency moves.** Firebase authentication, email OTP verification, phone verification, and biometric KYC — BVN cross-referenced against a live selfie — are built into account creation from day one, not bolted on as an afterthought.

**Schedule money like a calendar event.** Users can set a transfer to fire automatically at a future time. A background scheduler picks it up and executes it through the same secure ledger path as an instant transfer, with a safety window so an outage never causes a burst of stale payments to fire late and surprise anyone.

### Nova — the AI that actually understands your money

This is where NovaBanq stops looking like every other fintech pitch.

- **Type what you mean, get a transfer.** *"Send 5000 to david.ng"* or *"help me transfer 250 cedis to kwame.gh at 5pm"* is parsed into a structured transfer — recipient, amount, and optional future time — and turned into a one-tap confirmation. No dropdowns, no manual currency math.

- **Ask it anything about your own money.** "What's my balance," "who did I send money to last," "how much did I spend last month," "tell me about my transactions with Chidera," "am I spending too much" — Nova answers in plain, warm language, grounded entirely in the user's real transaction history.

- **Architected against hallucination — not just prompted against it.** This is the detail that matters to anyone who's seen an AI demo confidently make up a number. Nova's AI model never sees a user's account data directly. One model call classifies *what kind* of question was asked. Code — never the model — fetches the real number from the ledger. A second model call is only permitted to describe the exact numbers it was explicitly handed, and is instructed to cite nothing else. There is no code path in which Nova can invent a balance, because the model is never given the chance to.

- **Fails soft, never fails scary.** If the AI provider is briefly unreachable, a greeting still gets a warm reply — because nothing was at stake. But a real question about your balance gets an honest "please try again," never a friendly-sounding guess. Nova treats small talk and small talk tolerance the same way; it treats money questions with money-grade rigor.

### What's real, and what's intentionally simulated for this build

Every rail that doesn't require a live financial-institution partnership is real and running against a production backend today: authentication, KYC, the ledger, FX quoting, PIN security, transaction history, email notifications, and the entire Nova AI layer. The one piece simulated for the hackathon is the literal bank-settlement rail — the connection to a live payment provider for deposits and withdrawals, which requires commercial credentials we are finalizing post-hackathon. The virtual account issuance, webhook-based crediting, and ledger settlement architecture for that connection are already fully built and demonstrated end-to-end against a safe simulation harness — flipping it to a live provider is a configuration change, not a rebuild.

---

## 3. Impact & Value

### What makes NovaBanq different

| | Traditional bank wire | Typical money transfer operator | **NovaBanq** |
|---|---|---|---|
| Fee | Often 7%+ | Varies, frequently opaque | **Transparent 1%, shown before you confirm** |
| Speed | Days | Minutes to hours | **Seconds** |
| What you need to know | Bank name, account number, routing/SWIFT code | Agent location or bank details | **Just their `@tag`** |
| FX transparency | Rate often marked up silently | Varies by provider | **Live rate shown, locked for the confirm window** |
| Natural-language / AI | None | None | **Send and ask in plain language** |

### Measurable value

- NovaBanq's flat, disclosed fee directly targets the gap between the **8.4% average cost** of moving money in Sub-Saharan Africa and the **3% UN target** — and undercuts even the worst corridors, like South Africa–Zimbabwe's 12.7%, by a wide margin.
- Africa's cross-border payments market is projected to nearly triple to **$1 trillion by 2035**. NovaBanq is architected for that scale from the start — a real ledger and idempotency system, not a demo that would need to be rebuilt to handle real volume.
- Mobile money already moves **30% of Africa's cross-border transfers** at 1.5–3% fees, proving the continent will adopt a cheaper digital alternative when one exists with the right trust signals. NovaBanq combines that cost profile with bank-grade security and a richer product.
- With only **55% of African countries** currently permitting electronic KYC, NovaBanq's digital-first verification is built to work wherever that's possible today, and to degrade honestly — not silently — wherever it isn't yet.
- Remittances represent **more than 4% of GDP** in 19 African countries. The people receiving that money are disproportionately banked-light but smartphone-rich — exactly the population NovaBanq's tag-based, OTP-first onboarding is designed to reach without requiring a pre-existing bank relationship.

### The uniqueness

Plenty of products offer a digital wallet. Plenty offer cross-border transfers. A few are experimenting with AI chat layered on top of a banking app as a gimmick. **Almost none combine all three with real architectural rigor**: a tag-based identity system, an atomic multi-currency ledger that treats correctness as non-negotiable, and a conversational AI that can both *act* — actually execute a transfer — and *explain* — answer real financial questions — while being structurally prevented from making up the numbers it reports. That combination is NovaBanq's moat.

---

## 4. Target Users & Implementation

### Who NovaBanq is for

- **The cross-border family.** Sends support to relatives in another African country regularly, and is currently absorbing 7–12%+ in fees every single time.
- **The pan-African freelancer or small trader.** Invoices a client in Nairobi while based in Lagos, and needs to receive, hold, and eventually send money in more than one African currency without juggling five different banking apps.
- **The everyday user who wants one app for their money.** Prefers asking "how am I doing this month" and getting a real, honest answer over opening a spreadsheet.
- **The time-poor or less form-comfortable sender.** Wants to just say what they mean in plain language and have it happen — a real accessibility and convenience win, not just a novelty.

### Implementation roadmap

**Now — hackathon build.** Six-country, five-currency ledger with quote-then-confirm transfers, scheduled transfers, full transaction history, bank-grade onboarding (auth, OTP, phone, BVN + selfie KYC), transactional email notifications, and the complete Nova AI layer (parse, execute, and ask) — all running against a live backend, with deposit/withdrawal rails demonstrated through a safe simulation harness pending live provider credentials.

**0–3 months.** Connect the funding rail to a live payment provider for real virtual account issuance and signed webhook verification; ship withdrawals to bank accounts and mobile money; complete the remaining scheduled-transfer management endpoints; expand FX corridor coverage.

**3–6 months.** Extend Nova with recurring and list-style financial queries and richer spending insights; add voice input for natural-language transfers; run a structured pilot with a defined user cohort across two launch markets to validate retention and transaction frequency.

**6–12 months.** Formal compliance and licensing partnerships in each operating market; direct integrations with major mobile money rails; a lightweight disbursement API for the freelancer/small-trader segment; expansion beyond the initial six countries.

### Built on

FastAPI + Firestore for the backend and ledger, Firebase for authentication, Google Gemini for the Nova AI layer, Flutter for the mobile client, with Brevo for transactional email, Cloudinary for secure KYC image handling, and Prembly for BVN and biometric identity verification.

---

## 5. Team & Expertise

*[This section needs your team's real details filled in — don't submit with placeholders. For each of your 2–4 members, judges are specifically looking for: their name, their role on the project, and — most importantly — **which part of what's described above they actually built**, so the technical depth of this document is credibly backed by a real person. A template:]*

**[Full Name] — [Role, e.g. Backend Engineer]**
[1–2 sentences: what they built. e.g. "Designed and implemented the double-entry ledger engine, the idempotency system, and the FastAPI backend across all core money-movement endpoints."]

**[Full Name] — [Role, e.g. AI/ML Engineer]**
[e.g. "Built the Nova AI layer end-to-end — the natural-language transfer parser, the classify-then-answer question-answering pipeline, and the fail-soft error handling that keeps Nova honest when the model is grounded in real data."]

**[Full Name] — [Role, e.g. Mobile/Frontend Engineer]**
[e.g. "Built the Flutter client, including the transfer confirmation flow, the Nova chat interface, and the onboarding/KYC screens."]

**[Full Name] — [Role, e.g. Product/Design]**
[e.g. "Owned the problem research, the @tag UX concept, and the pricing-transparency design that shapes the whole product."]

---

## Appendix

- **Live API:** https://novabanq-api.onrender.com
- **Interactive API docs:** https://novabanq-api.onrender.com/docs
- **Full endpoint contract:** `docs/api-contract.md`
- **AI implementation reference:** `docs/ai_implementation.md`
- **[Demo video link — add before submission]**
- **[GitHub repository link — add before submission]**

---

## Sources

- World Bank Remittance Prices Worldwide data, as reported via TransUnion, "Driving Financial Inclusion — The Future of Cross-Border Payments in Africa," and Africa.com, "How Cross-Border Payments Can Unlock Africa's Financial Future" (Q1 2024 SSA remittance cost figures, GDP dependency figures).
- IMF–World Bank Group Technical Assistance Report (2025), on the South Africa–Zimbabwe remittance corridor cost.
- The Guardian (Tanzania) / Oui Capital report, "Africa's cross-border payments to hit $1trn by 2035" (market size projections, mobile money share, electronic KYC adoption rate).
- AfricaNenda Foundation / World Bank / UNECA, "State of Inclusive Instant Payment Systems (SIIPS) Report" 2025, via AllAfrica (instant payment transaction volume growth).
"""NovaBanq API application entry point.

Builds the FastAPI application, wires middleware, registers exception
handlers, and mounts the versioned API router.

Background scheduler:
    A single APScheduler ``BackgroundScheduler`` runs inside this
    process and fires due scheduled transfers every 30 seconds. The
    scheduler job calls ``scheduled_service.execute_due``, the same
    function ``scripts/run_scheduler.py`` calls — that script remains
    for local testing and debugging, but is redundant in any
    deployment that runs the API (this process).

    The scheduler runs in a background thread of the same process as
    uvicorn. It does not need a second terminal or a separate Render
    service. This is deliberate: the scheduler is a part of the API
    process because that is where the ledger, the accounts service,
    and the notifications service already live, and the callback
    reuses them directly.

    Restart safety: if uvicorn restarts while a scheduled transfer is
    mid-execution, the ``execute_due`` call is lost. The next pass
    after restart re-runs the same transfer; the ledger's deterministic
    idempotency key (derived from the scheduled_transfer_id) dedupes
    the second attempt, and ``_fire_one``'s DuplicateTransferError
    recovery marks the scheduled transfer SETTLED using the
    transaction id from the ledger's idempotency record. So a restart
    cannot double-settle a transfer, and cannot leave one stranded in
    PENDING after the money has moved.

    Multi-worker safety: if uvicorn is ever run with ``--workers N``,
    each worker will start its own scheduler instance, and they will
    all poll Firestore. Two schedulers firing the same due transfer
    dedupe at the ledger (same deterministic key) and one loses the
    ``mark_settled`` race with a logged CRITICAL. No double-spend —
    just a loud log line. For the demo, run a single worker.
"""

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.constants import SCHEDULED_TRANSFER_BATCH_SIZE
from app.core.exception_handlers import register_exception_handlers
from app.core.exceptions import NovaBanqError
from app.features.transfers import scheduled_service
from app.infra.firebase.client import get_firebase_app


logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

# httpx logs the full URL of every outbound request at INFO level —
# including any query parameters. Vendors that accept API keys as a
# query string (rather than a header) would leak those keys into this
# log, and every log shipper that collects it. We send our FX vendor's
# key in a header specifically to keep it out of the URL, but silencing
# httpx's INFO chatter here is defense in depth: if a future client
# ever puts a secret in a query param, it still won't reach the logs.
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# How often the in-process scheduler polls for due transfers. Matches
# ``scripts/run_scheduler.POLL_INTERVAL_SECONDS`` so the script and
# the in-process scheduler behave identically when both are running.
_SCHEDULER_INTERVAL_SECONDS = 30


def _run_scheduler_pass() -> None:
    """One scheduler pass, wrapped for the background scheduler.

    Called by APScheduler on its own thread. Catches every exception
    so a single failed pass cannot kill the scheduler thread — an
    uncaught exception inside an APScheduler job is logged by the
    library but the job's next invocation still runs. This wrapper
    makes the log specific to the scheduler and keeps the failure
    handling in one place.

    The exact same logic as ``scripts/run_scheduler._one_pass`` plus
    the same error handling ``scripts/run_scheduler.main`` applies in
    its loop. Duplicated rather than imported because the script is a
    CLI tool with its own logging and its own lifecycle; pulling that
    into an importable form to save eight lines would couple the
    server process to a script.
    """
    try:
        processed = scheduled_service.execute_due(
            batch_size=SCHEDULED_TRANSFER_BATCH_SIZE,
        )
        if processed > 0:
            logger.info(
                "Scheduler pass processed %d scheduled transfer(s).",
                processed,
            )
    except NovaBanqError as exc:
        # Infrastructure failure — Firestore unreachable, FX provider
        # down. Log the specific error code and move on; the next
        # 30-second tick retries.
        logger.error(
            "Scheduler pass failed: [%s] %s.",
            exc.code.value,
            exc.message,
        )
    except Exception:  # noqa: BLE001
        # A truly unexpected error — a bug, an SDK surprise. Log the
        # full traceback so it's diagnosable, then let the next tick
        # try again. A scheduler thread that dies silently is worse
        # than one that keeps failing loudly.
        logger.exception("Scheduler pass raised an unexpected error.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: runs on startup and shutdown."""
    logger.info(
        "Starting %s v%s (env=%s, demo_mode=%s).",
        settings.app_name,
        settings.app_version,
        settings.app_env,
        settings.demo_mode,
    )
    firebase_app = get_firebase_app()
    logger.info("Firebase project connected: %s", firebase_app.project_id)

    # Start the in-process scheduler. Runs ``_run_scheduler_pass`` on
    # an interval in a background thread. ``replace_existing=True``
    # makes startup idempotent if the lifespan ever fires twice in a
    # single process (it shouldn't, but the argument is cheap).
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _run_scheduler_pass,
        trigger="interval",
        seconds=_SCHEDULER_INTERVAL_SECONDS,
        id="scheduled_transfer_pass",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info(
        "Scheduled-transfer worker started (interval=%ds).",
        _SCHEDULER_INTERVAL_SECONDS,
    )

    yield

    # Shut the scheduler down before the process exits. ``wait=False``
    # means we don't block on a pass that's mid-execution — the
    # DuplicateTransferError recovery path handles a settled-but-
    # unmarked transfer on the next startup, so an abrupt stop here is
    # safe.
    scheduler.shutdown(wait=False)
    logger.info("Scheduled-transfer worker stopped.")
    logger.info("Shutting down %s.", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    description="""
# Sending money from one African country to another is slow, costly, and confusing. NovaBanq fixes it.

## The problem, in simple words

Let's say Kwame lives in Accra, Ghana. His friend David lives in Lagos, Nigeria. Kwame wants to send David 500 cedis.

This should be easy. It is not. Today, this is what Kwame has to do:

1. Open his bank app and choose which currency to send in.
2. Open another app, or Google, to check today's cedi to naira rate. He does this because he does not trust the rate the bank shows him.
3. Do the maths by himself, so he knows how much naira David will really get.
4. Ask David for his bank account details and type them in by hand. One wrong number and the money goes to the wrong person.
5. Pay a fee that he only understands after the money has left his account.
6. Wait. It can take hours. Sometimes it takes days.

At the end of all this, **David does not get what Kwame thought he was sending.** About 9 out of every 100 cedis are lost along the way.

## Where does the money go?

This is the part most people do not know.

**There is no direct road for money between Ghana and Nigeria.**

When Kwame sends cedis, the money does not go straight from Accra to Lagos. It first travels to **London or New York**. There, the cedis are changed to dollars or pounds. Then the dollars or pounds are changed to naira. Then the money travels back to Africa.

Every stop takes a cut. Every change of currency costs money. So Kwame and David, who live in two neighbouring countries, are joined by a money route that goes around the world. They pay for that long trip, even though the money never needed to leave Africa.

## The second problem: a cost you cannot see

There is another way people lose money, and it is harder to notice. Many banks and older money apps do not show their full price as a fee. They hide part of it inside the exchange rate.

Here is a simple example. Say the real market rate is 100 naira for every 1 cedi. The app gives Kwame only 95 naira for each cedi. On 500 cedis:

- At the real rate, David should get ₦50,000.
- At the app's rate, David gets ₦47,500.
- The missing ₦2,500 was never shown as a fee. It was taken quietly through the rate.

So an app can say "no transfer fee" and still take a cut. The numbers above are simple ones, only to show the idea. This is why Kwame does not trust the rate his bank shows him, and why he checks a second app.

NovaBanq shows the rate and the 1% fee before you confirm, so you know what David will get before any money moves.

## How bad is it?

The World Bank has been checking the cost of sending money for more than fifteen years. This is what it found:

- Sub-Saharan Africa is **the most expensive region in the world** to send money to. It has held this position almost every year.
- The average fee in the region is **8.46%**. The world average is **6.36%**.
- On the **Ghana to Nigeria** route (the same route as our example), the World Bank found **no service at all** that was fast, clear, and fairly priced. It is one of about twenty routes in the world with this problem.
- On a real transfer, about **8.9%** of the money is lost on the way.

Let's put this in cedis. If Kwame sends 500 cedis, about **GH₵42 is lost** to fees and bad exchange rates. With NovaBanq's 1% fee, he pays about **GH₵5**.

## The problem nobody has closed

Many apps can move money between countries. But almost all of them leave the hard part to the person sending:

- You still choose the currency.
- You still check the rate.
- You still do the maths.
- You still type a long bank account number.

And on the Ghana to Nigeria route, the World Bank found no service that was fast, clear, and fairly priced. That is the gap.

**NovaBanq closes this gap by taking the work away from the user:**

1. **Each person only sees their own money.** The sender sees cedis. The receiver sees naira. Nobody picks a currency.
2. **The money moves inside NovaBanq.** It does not travel through London or New York, so the long and costly route is gone.
3. **You send by typing a sentence.** "send 500 cedis to david.ng" is all it takes. Nova finds the receiver, checks the live rate, and shows the result before you confirm.

Cheaper fees are only part of the answer. The real fix is that the user no longer has to think about currency, rates, or maths at all.

## Who pays for this?

Mostly normal families. Most money sent between African countries is not business money. It is:

- A parent paying school fees.
- A brother sending rent money.
- A daughter working in another country, sending money home.

Every percent that is lost is money that does not reach a home that needed it. The people who can least afford to lose it are the ones who lose it.

---

# What NovaBanq does about it

## The idea: nobody has to think about currency

In NovaBanq, **every person has one account, in the money of their own country.** Every person also gets a short tag that shows which country they are in.

- Kwame lives in Ghana. His tag is `@kwame.gh`. His account holds **cedis**.
- David lives in Nigeria. His tag is `@david.ng`. His account holds **naira**.

Now see what happens when Kwame sends money to David:

1. Kwame types: **"send 500 cedis to david.ng"**
2. NovaBanq tells him what will happen: *"David will receive about ₦56,749 at today's rate."*
3. Kwame enters his PIN.
4. **Kwame pays 500 cedis plus the 1% fee (5 cedis). ₦56,749 enters David's account.**

**Kwame only sees cedis. David only sees naira.**

Kwame does not need to trust or check a naira number from another app. David does not see cedis, and he does not need to work out what they are worth. The money is changed by NovaBanq, inside the transfer, at the live rate. Each person sees the result in their own money.

## The old way and the NovaBanq way

| | The old way | NovaBanq |
|---|---|---|
| Choosing a currency | You must choose one | Nobody chooses. Each person sees their own currency |
| Checking the rate | You open another app to compare | NovaBanq uses the live rate for you |
| Doing the maths | You do it by hand | NovaBanq shows what the other person will get, before you confirm |
| Receiver details | You type a long bank number from an old WhatsApp message | You type a short tag, like `david.ng` |
| The fee | Spread across many places, hard to know the total | One flat fee of **1%**, shown before you confirm |
| Speed | Hours or days | Seconds |
| The route | Ghana to London to Nigeria | Ghana to Nigeria, inside NovaBanq |

## Why is our fee so low?

NovaBanq keeps its own record of who has how much money. This record is called a **ledger**. When Kwame sends money to David, the money does not travel around the world. It just moves from one NovaBanq account to another. That costs us almost nothing, so we charge **1% flat**, not the 8.46% that the region pays today.

The money you save stays with your family. It does not go to a middleman in another part of the world.

**We do not hide anything in the exchange rate.** The rate is the market rate from our FX provider, passed on as it is, with no markup added. The 1% fee is a separate line, added on top of what the sender sends. So David always gets the full converted amount, and Kwame can see exactly what he pays.

**Money enters through a virtual account issued by our payment provider** — Flutterwave in production, a deterministic mock in the demo. **Withdrawals are the next feature on the roadmap**; the ledger is already built to support them, and Paystack is one of the providers we'd consider for corridors Flutterwave doesn't cover.

## Why do you type a sentence, and not fill a form?

Other money apps give you a form. The form is where the confusion starts: which currency, which rate, which account number.

In NovaBanq, sending money is a chat. Our AI assistant, **Nova**, reads your sentence, finds the receiver, checks the live rate, and tells you what is about to happen. You confirm with your PIN.

**Nova can suggest a transfer, but Nova can never move money.** Only the user's PIN can do that, and the AI never sees the PIN. The real movement of money is done by a separate, strict system.

---

## Can you trust it with real money? (For the technical judges)

Under the chat, NovaBanq has a proper double-entry ledger. This is the same idea that banks use.

- **5-step atomic transactions** for transfers between currencies. All the steps finish together, or none of them do.
- **Idempotency keys inside the Firestore transaction.** If the same request is sent twice, the money moves only once.
- **Safe scheduled transfers.** If the server restarts in the middle of a scheduled transfer, it continues safely and cannot pay twice.
- **bcrypt-hashed PINs with lockout** after too many wrong tries.
- **Transactional status checks.** If a cancel and a scheduled send happen at the same time, a transfer can never be left half done.

Our rule: **the AI proposes, the ledger decides.** This rule is enforced in the code, not just in a prompt. You can read it in [the repo](https://github.com/Lanhubs/novabanq).

---

## 🚀 Try it in your browser now (30 seconds, no install)

📱 **[Launch the Flutter app in your browser](https://appetize.io/app/b_2xkrdxr27mcqlv5gy2iyj7ix3e?device=pixel7&osVersion=13.0&toolbar=true)** · 🔁 **[Backup link](https://appetize.io/app/b_vo77v2vpnudkp22cu57ld4vkya)** · 📂 **[Source code](https://github.com/Lanhubs/novabanq)**

### Demo account (Ghana sender, already funded)
- Email: `codewithkakes@gmail.com`
- Password: `test1234`
- Transaction PIN: `48392`

### Send to either of these Nigerian accounts
- **`david.ng`**
- **`olanrewaju.ng`**

**Try this in the AI chat:** type **"send 500 cedis to david.ng"**. Nova will show you how much naira David will receive. Enter the PIN and the transfer is done. You will not see a currency picker at any point.

### 🎬 Watch the 3-minute walkthrough
**[Signup, funding, transfer, and AI-driven send, from start to finish](https://drive.google.com/drive/folders/1Qv1d_wtG3QHSXKrNp8RaZ7UakylZZdAi?usp=drive_link)**

💡 **Note for the judges:** the video shows the smooth visual flow and the AI interface. Everything underneath is real — every button press in the video fires an actual 5-leg atomic ledger transaction, writes real state to Firestore, and updates the wallet through the same backend you see documented below. Nothing in the video is a mock-up of a product; it's the product.

---

## 🔬 Try the AI directly, without the app

**`POST /api/v1/ai/ask`** answers plain questions using the user's own transaction history. Try: *"what's my balance"*, *"who did I send to last"*, *"who has sent me money"*, *"did my scheduled transfer go out"*. If you type a transfer command, it gives back a confirmation that is ready to execute.

**`POST /api/v1/ai/execute-transfer`** takes the confirmed transfer and the PIN, and completes it. It is idempotent. The receiver is checked and the PIN is checked. Either the transfer goes through, or the user gets a clear error message.

Every endpoint is documented below.

---

## 🛠️ Who built NovaBanq

**Daniel Clement Toluwalase, Founder and UI/UX Designer.** Designed the whole NovaBanq experience: the flow, the screens, and the look.

**Kakes David, Software Engineer, Backend Engineer, and CTO.** Built and runs the whole backend: the ledger, the transfers engine, the FX rate cache, the AI intent parser, Nova, the scheduled-transfer worker, and every API endpoint on this page. [See it in the repo.](https://github.com/Lanhubs/novabanq)

**Habeeb Mohammed Olanrewaju, Frontend Developer.** Built the Flutter app that you can open in your browser through the Appetize link above.

---

**A Ghanaian sends cedis. A Nigerian receives naira. Nobody picks a currency, checks a rate, or does any maths. That is NovaBanq.**

**Built by Daniel, Kakes, and Habeeb. For Africa.**
""",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(api_router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    """Liveness probe. Returns app status and current environment."""
    return {
        "success": True,
        "data": {
            "status": "ok",
            "app": settings.app_name,
            "version": settings.app_version,
            "env": settings.app_env,
            "demo_mode": settings.demo_mode,
        },
        "error": None,
    }
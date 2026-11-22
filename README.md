# SignoffQuorum

A signed sheet is not a quorum until the names are counted. An on-chain counter for
approvals that arrive as prose, against a roster and a threshold fixed at deploy.

    document  ->  [ contract numbers the sentences, model names one per approver ]
              ->  code checks name and yes  ->  QUORUM | SHORT | UNUSABLE

Approvals still arrive as prose: a board resolution, a change advisory note, an expense
sheet, a vendor sign-off page. Whoever reads it counts names in their head, and three
mistakes keep happening. A name that is not on the roster gets counted. The same person
appearing twice is counted twice. A sentence that names someone who objected is counted as
an approval because their name is on it. This contract makes each of the three impossible
to do silently.

## Live on Studio

    contract       0x5DE0FE9bBBBdea74B9F2a380e2159a0F29C12E11
    explorer       https://explorer-studio.genlayer.com/address/0x5DE0FE9bBBBdea74B9F2a380e2159a0F29C12E11
    deploy tx      0xeae807d912c055b39012926929e62541251d8dea004ad410b9fe88e56a794c05
    owner          0x74b60694EfBBCF6B5F78240Ed61139282b4C17A9
    site_label     board-2026
    roster         alice:Alice Chen, bob:Bob Ruiz, carol:Carol Diaz
    needed         2 of 3

Three cases were checked against that roster and every branch is live:

| case | what the document shows | verdict | signed | missing | counts | is_quorate |
| --- | --- | --- | --- | --- | --- | --- |
| `vote-114` | Alice and Bob approved, Carol asked for the minutes | `QUORUM` | `alice,bob` | `carol` | `2,2` | `true` |
| `vote-115` | Alice approved, Bob asked for a copy, Carol objected | `SHORT` | `alice` | `bob,carol` | `1,2` | `false` |
| `vote-116` | Alice twice, plus two non-approvals | `SHORT` | `alice` | `bob,carol` | `1,2` | `false` |

`is_quorate` also returns `false` for a case id that was never registered.

## Why the sentence number and not the quote

The first deploy of this contract compared the quoted text between validators. Four of five
nodes read `QUORUM` and one read it too, yet the transaction was rejected: the strings they
compared differed by a trailing period. The fix is in the design, not in the prompt. The
contract splits the document into numbered sentences itself, the model only says *which
number*, and the compared value is `alice=s2|bob=s3`. Two nodes that quote different pieces
of the same sentence land on the same integer, and `unit_text` still lets anyone read the
sentence afterwards:

    line_of("vote-114", "alice")  -> s2
    unit_text("vote-114", 2)      -> "approved alice chen"

## A signoff counts only if

1. the code is on the roster. A signer outside it is never counted, and never poisons the
   reading;
2. the number exists and the sentence contains that person's name, so a name cannot be
   borrowed across lines;
3. the sentence contains one of the fixed approval words in `APPROVAL_WORDS`, so
   "Carol Diaz objected" and "Bob Ruiz asked for a copy" are not approvals;
4. the person has not already been counted. A person listed twice loses both entries, so
   two weak lines cannot be stacked into one approval.

The verdict is `QUORUM` when distinct counted signers reach `needed`, `SHORT` otherwise with
the missing codes named, and `UNUSABLE` when the reading itself cannot be trusted.

## What is deterministic and what is not

The model says which numbered sentence shows a named person approving. It never sees the
words QUORUM, SHORT or UNUSABLE, cannot add anyone to the roster, cannot change `needed`, and
cannot mark anyone as approved without a sentence that code then re-checks.

Consensus owns one value: the surviving `code=sN` pairs, or `UNUSABLE`. Filtering happens in
code in every node before anything is compared, so a bad line is dropped identically
everywhere; the verdict, the signed list, the missing list and the counts are re-derived from
the agreed pairs plus the roster and `needed`.

## The roster is immutable on purpose

There is no `add_signer`, no `set_needed` and no `remove_signer`. A roster that can grow
after the document was written is a roster that can be fitted to the document, so the entire
list and the threshold arrive in the constructor and never move again.

## Surface

    check(case_id, text)        one reading, one verdict, once per case id

Consumer views:

    is_quorate(case_id)         the only boolean downstream should read; fails closed
    verdict_of(case_id)         QUORUM | SHORT | UNUSABLE, "" before the check
    signed_of(case_id)          sorted codes that were counted
    missing_of(case_id)         sorted roster codes that were not
    counts_of(case_id)          "<distinct signed>,<needed>"
    line_of(case_id, signer)    s3 for the sentence that counted, "" when it did not

Audit views:

    unit_count_of(case_id)      how many sentences the contract numbered
    unit_text(case_id, n)       the exact sentence behind number n
    text_of(case_id)            the registered document

Rule views: `roster_of`, `roster_name_of`, `signer_count`, `needed`, `case_count`,
`site_name`, `config`.

Using it from another contract is one question with one safe answer:

    if other.is_quorate("vote-114"):
        self._release()

## Bounds and refusals

    MAX_ROSTER      9 signers          MIN_ROSTER      2
    MAX_UNITS       80 sentences       MAX_TEXT        4000 characters
    MAX_CASES       500                MAX_QUOTE       200 characters

Errors: `BAD_SITE_LABEL, BAD_ROSTER, BAD_SIGNER, BAD_NAME, ROSTER_DUP, BAD_NEEDED,
BAD_CASE_ID, CASE_EXISTS, TOO_MANY_CASES, BAD_TEXT, NO_UNITS, TOO_MANY_UNITS`.

A document with more than 80 sentences is refused, never trimmed. An honest empty answer is
`{"approvals": []}` and that is `SHORT` with everyone missing, not `UNUSABLE`. A quote that
sits in two different sentences is a guess, so it is dropped rather than resolved.

## Tests

47 direct-mode tests, no network, GenVM in memory:

    python -m pytest tests/direct -q
    47 passed

Covered: each verdict branch, the duplicate rule, the borrowed-name rule, the approval-word
rule, non-roster signers, numbers outside the document, quote-only readings, ambiguous
quotes, quote/number contradictions, every UNUSABLE shape, the validator agreeing and
rejecting (including the case that broke the first live deploy), owner-free immutable roster,
bounds, and the fail-closed gate.

Gates before deploy:

    genvm-lint lint        Lint passed (3 checks)
    genvm-lint validate    SignoffQuorum, 17 methods (16 view, 1 write)
    genvm-lint typecheck   No type errors found

## Deliberate limits

An approval word list cannot read sarcasm, and a roster cannot know whether the person who
signed had the authority to. What this contract does is narrower and checkable: it makes the
count over *people* instead of over *lines*, binds every counted signoff to one numbered
sentence that contains that person's name and a yes, and refuses to guess when the reading is
ambiguous.

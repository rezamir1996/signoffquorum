# Evidence

Everything below was read back from Studio and from the chain, not copied from a screenshot.

    contract     0x5DE0FE9bBBBdea74B9F2a380e2159a0F29C12E11
    explorer     https://explorer-studio.genlayer.com/address/0x5DE0FE9bBBBdea74B9F2a380e2159a0F29C12E11
    owner        0x74b60694EfBBCF6B5F78240Ed61139282b4C17A9
    site_label   board-2026
    roster       alice:Alice Chen, bob:Bob Ruiz, carol:Carol Diaz
    needed       2 of 3

## Transactions, in the order they happened

| # | what | tx hash | outcome |
| --- | --- | --- | --- |
| 1 | deploy, first draft (quotes compared) | `0x30c750f4a6fc979d4c864d355d670f378b89a39a40293fda5ebf3e36e4a12887` | FINALIZED, contract `0x203164ebA416713A1039A1D42D7A0E655b5b5411` |
| 2 | `check vote-114` on the first draft | `0x73a6a7ed07a199a4fe16c5961b7448e7f6347b45ec1c648cd8a5d54a90968351` | **rejected**: validators disagreed over a trailing period |
| 3 | deploy, fixed draft (sentence numbers compared) | `0xeae807d912c055b39012926929e62541251d8dea004ad410b9fe88e56a794c05` | FINALIZED, contract `0x5DE0FE9bBBBdea74B9F2a380e2159a0F29C12E11` |
| 4 | `check vote-114` | `0xc84946ed8e4abc09c681a6969df25e9154b48d59716125cfc89d13fd9150ea9b` | FINALIZED, 3 agree |
| 5 | `check vote-115` | `0x8904f396f34026b7e0bc1ff8ae0ec9eac5eaa5e6df6b8706560a9f75f664b051` | FINALIZED, majority agree |
| 6 | `check vote-116` | `0xd45ecbbda4c0cd0678081e5877f5d26bf6504913004dc217a0a55002cda95333` | FINALIZED, majority agree |

Transaction 2 is part of the evidence, not a footnote. Four of five nodes read `QUORUM`,
every node read the document correctly, and the transaction was still rejected because the
compared value was the quoted string and two honest nodes ended it with a different number of
periods. The contract was redeployed with the compared value changed to the sentence number,
which is the whole design lesson:

    before   OK:alice=Approved: Alice Chen.|bob=Approved: Bob Ruiz.
    after    OK:alice=s2|bob=s3

## State read back from 0x5DE0FE9bBBBdea74B9F2a380e2159a0F29C12E11

    config()     'board-2026|3 signers|2 needed|3 cases'
    roster_of()  'alice,bob,carol'
    needed()     2
    signer_count() 3
    case_count() 3

| view | `vote-114` | `vote-115` | `vote-116` |
| --- | --- | --- | --- |
| `verdict_of` | `QUORUM` | `SHORT` | `SHORT` |
| `signed_of` | `alice,bob` | `alice` | `alice` |
| `missing_of` | `carol` | `bob,carol` | `bob,carol` |
| `counts_of` | `2,2` | `1,2` | `1,2` |
| `is_quorate` | `True` | `False` | `False` |

`is_quorate("never-registered")` returns `False`, `verdict_of` returns `""`, and
`line_of("never-registered", "alice")` returns `""`.

`vote-116` is the duplicate case: Alice appears twice in that document and is counted once,
which is why a document with two "Approved: Alice Chen" lines and nothing else is `SHORT`
with `1,2` rather than a quorum.

## The audit path for one signoff

    line_of("vote-114", "alice")  -> s2
    line_of("vote-114", "bob")    -> s3
    unit_count_of("vote-114")     -> 4
    unit_text("vote-114", 2)      -> "approved alice chen"
    unit_text("vote-114", 3)      -> "approved bob ruiz"
    unit_text("vote-114", 4)      -> "carol diaz asked for the minutes"

The verdict says Alice counts on sentence 2; sentence 2 is readable by anyone, and it is the
sentence that contains her name and the word `approved`. Sentence 4 contains Carol's name and
no approval word, which is why Carol is named in `missing_of`.

## Source integrity

The code in deploy transaction 3 was decoded from the transaction payload and compared to
`contracts/signoff_quorum.py` on `main`: 20768 bytes against 20769, identical apart from
`\r\n` line endings and the final newline that Studio drops. It contains `_locate` and
`case_lines`, so the sentence-number draft is what is actually running. ASCII only.

Gates before that deploy: 47 direct-mode tests passed, `genvm-lint lint` clean,
`genvm-lint validate` reports 17 methods (16 view, 1 write), `genvm-lint typecheck` clean.

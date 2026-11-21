"""Direct-mode tests for SignoffQuorum. No network, no Studio: the GenVM runs in memory.

ASCII only.
"""

import pytest

ROSTER = "alice:Alice Chen,bob:Bob Ruiz,carol:Carol Diaz"
PROMPT = r"(?s).*THE ONLY PEOPLE WHO CAN APPROVE.*"

ALL_DOC = (
    "Prepared for the board. Approved: Alice Chen. "
    "Approved: Bob Ruiz. Approved: Carol Diaz."
)

TWO_DOC = (
    "Prepared for the board. Approved: Alice Chen. "
    "Approved: Bob Ruiz. Carol Diaz asked for the minutes."
)

ONE_DOC = (
    "Prepared for the board. Approved: Alice Chen. "
    "Bob Ruiz asked for a copy. Carol Diaz objected to the schedule."
)

DUP_DOC = (
    "Prepared for the board. Approved: Alice Chen. "
    "Approved: Alice Chen again. Bob Ruiz asked for a copy."
)

BUNDLE_DOC = (
    "Prepared for the board. Approved: Alice Chen and Bob Ruiz. "
    "Carol Diaz asked for the minutes."
)


def _gate(direct_deploy, needed="2"):
    return direct_deploy("contracts/signoff_quorum.py", "board", ROSTER, needed)


def _answers(*pairs):
    parts = []
    for code, quote in pairs:
        parts.append('{"signer": "' + code + '", "quote": "' + quote + '"}')
    return '{"approvals": [' + ", ".join(parts) + "]}"


# ------------------------------------------------------------ the counted quorum
def test_two_of_three_approvals_is_a_quorum(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    direct_vm.mock_llm(
        PROMPT, _answers(("alice", "Approved: Alice Chen"), ("bob", "Approved: Bob Ruiz"))
    )

    assert gate.check("c1", TWO_DOC) == "QUORUM"
    assert gate.signed_of("c1") == "alice,bob"
    assert gate.missing_of("c1") == "carol"
    assert gate.counts_of("c1") == "2,2"
    assert gate.is_quorate("c1") is True


def test_one_approval_against_a_threshold_of_two_is_short(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    direct_vm.mock_llm(PROMPT, _answers(("alice", "Approved: Alice Chen")))

    assert gate.check("c2", ONE_DOC) == "SHORT"
    assert gate.signed_of("c2") == "alice"
    assert gate.missing_of("c2") == "bob,carol"
    assert gate.counts_of("c2") == "1,2"
    assert gate.is_quorate("c2") is False


def test_three_approvals_against_a_threshold_of_three(direct_vm, direct_deploy):
    gate = _gate(direct_deploy, needed="3")
    direct_vm.mock_llm(
        PROMPT,
        _answers(
            ("alice", "Approved: Alice Chen"),
            ("bob", "Approved: Bob Ruiz"),
            ("carol", "Approved: Carol Diaz"),
        ),
    )

    assert gate.check("c3", ALL_DOC) == "QUORUM"
    assert gate.signed_of("c3") == "alice,bob,carol"
    assert gate.missing_of("c3") == ""
    assert gate.counts_of("c3") == "3,3"


def test_the_same_person_twice_is_not_two_approvals(direct_vm, direct_deploy):
    """The counted quorum is over people, not over lines."""
    gate = _gate(direct_deploy)
    direct_vm.mock_llm(
        PROMPT,
        _answers(("alice", "Approved: Alice Chen"), ("alice", "Approved: Alice Chen again")),
    )

    assert gate.check("c4", DUP_DOC) == "SHORT"
    assert gate.signed_of("c4") == ""
    assert gate.counts_of("c4") == "0,2"
    assert gate.is_quorate("c4") is False


def test_one_line_that_names_two_people_approves_both(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    line = "Approved: Alice Chen and Bob Ruiz"
    direct_vm.mock_llm(PROMPT, _answers(("alice", line), ("bob", line)))

    assert gate.check("c5", BUNDLE_DOC) == "QUORUM"
    assert gate.signed_of("c5") == "alice,bob"
    assert gate.quote_of("c5", "alice") == line
    assert gate.quote_of("c5", "bob") == line


# ---------------------------------------------------- every line is re-checked
def test_a_line_that_is_not_in_the_document_is_dropped(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    direct_vm.mock_llm(
        PROMPT,
        _answers(("alice", "Approved: Alice Chen at nine"), ("bob", "Approved: Bob Ruiz")),
    )

    assert gate.check("d1", TWO_DOC) == "SHORT"
    assert gate.signed_of("d1") == "bob"
    assert gate.quote_of("d1", "alice") == ""


def test_a_line_that_does_not_name_the_signer_is_dropped(direct_vm, direct_deploy):
    """A name cannot be borrowed: Alice cannot be approved by a line about Bob."""
    gate = _gate(direct_deploy)
    direct_vm.mock_llm(
        PROMPT, _answers(("alice", "Approved: Bob Ruiz"), ("bob", "Approved: Bob Ruiz"))
    )

    assert gate.check("d2", TWO_DOC) == "SHORT"
    assert gate.signed_of("d2") == "bob"
    assert gate.counts_of("d2") == "1,2"


def test_a_line_without_an_approval_word_is_dropped(direct_vm, direct_deploy):
    """"Carol Diaz objected to the schedule" is a line with a name and no yes in it."""
    gate = _gate(direct_deploy)
    direct_vm.mock_llm(
        PROMPT,
        _answers(("alice", "Approved: Alice Chen"), ("carol", "Carol Diaz objected")),
    )

    assert gate.check("d3", ONE_DOC) == "SHORT"
    assert gate.signed_of("d3") == "alice"
    assert gate.missing_of("d3") == "bob,carol"


def test_a_signer_outside_the_roster_is_never_counted(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    direct_vm.mock_llm(
        PROMPT,
        _answers(("dave", "Approved: Alice Chen"), ("alice", "Approved: Alice Chen")),
    )

    assert gate.check("d4", TWO_DOC) == "SHORT"
    assert gate.signed_of("d4") == "alice"
    assert gate.missing_of("d4") == "bob,carol"


def test_a_line_too_short_to_mean_anything_is_dropped(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    direct_vm.mock_llm(PROMPT, _answers(("alice", "yes"), ("bob", "Approved: Bob Ruiz")))

    assert gate.check("d5", TWO_DOC) == "SHORT"
    assert gate.signed_of("d5") == "bob"


def test_every_counted_line_is_readable_from_the_chain(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    direct_vm.mock_llm(
        PROMPT, _answers(("alice", "Approved: Alice Chen"), ("bob", "Approved: Bob Ruiz"))
    )
    gate.check("d6", TWO_DOC)

    assert gate.quote_of("d6", "alice") == "Approved: Alice Chen"
    assert gate.quote_of("d6", "bob") == "Approved: Bob Ruiz"
    assert gate.quote_of("d6", "carol") == ""
    assert gate.quote_of("d6", "nobody") == ""
    assert gate.text_of("d6") == TWO_DOC


# ------------------------------------------------------------ unusable readings
def test_prose_instead_of_answers_is_unusable(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    direct_vm.mock_llm(PROMPT, "The board approved everything, it looks fine to me.")

    assert gate.check("u1", ONE_DOC) == "UNUSABLE"
    assert gate.signed_of("u1") == ""
    assert gate.missing_of("u1") == "alice,bob,carol"
    assert gate.counts_of("u1") == "0,2"
    assert gate.is_quorate("u1") is False
    assert gate.quote_of("u1", "alice") == ""


def test_a_payload_without_approvals_is_unusable(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    direct_vm.mock_llm(PROMPT, '{"map": "alice"}')

    assert gate.check("u2", ONE_DOC) == "UNUSABLE"


def test_an_approval_that_is_not_an_object_is_unusable(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    direct_vm.mock_llm(PROMPT, '{"approvals": ["alice"]}')

    assert gate.check("u3", ONE_DOC) == "UNUSABLE"


def test_a_quote_that_is_not_a_string_is_unusable(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    direct_vm.mock_llm(PROMPT, '{"approvals": [{"signer": "alice", "quote": 7}]}')

    assert gate.check("u4", ONE_DOC) == "UNUSABLE"


def test_an_empty_answer_is_a_reading_that_proves_nothing(direct_vm, direct_deploy):
    """Nobody approved is not a broken reading: it is SHORT with everyone missing."""
    gate = _gate(direct_deploy)
    direct_vm.mock_llm(PROMPT, '{"approvals": []}')

    assert gate.check("u5", ALL_DOC) == "SHORT"
    assert gate.signed_of("u5") == ""
    assert gate.missing_of("u5") == "alice,bob,carol"
    assert gate.counts_of("u5") == "0,2"


def test_a_checked_case_is_recorded(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    direct_vm.mock_llm(PROMPT, _answers(("alice", "Approved: Alice Chen")))
    gate.check("u6", ONE_DOC)
    assert gate.verdict_of("u6") == "SHORT"
    assert gate.case_count() == 1


# -------------------------------------------------------------------- validator
def test_validator_agrees_when_the_lines_match(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    direct_vm.mock_llm(
        PROMPT, _answers(("alice", "Approved: Alice Chen"), ("bob", "Approved: Bob Ruiz"))
    )
    gate.check("v1", TWO_DOC)

    assert direct_vm.run_validator() is True


def test_validator_rejects_a_line_the_leader_invented(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    direct_vm.mock_llm(PROMPT, _answers(("alice", "Approved: Alice Chen")))
    gate.check("v2", ONE_DOC)

    forged = {"signal": "OK:alice=Approved: Alice Chen|bob=Approved: Bob Ruiz"}
    assert direct_vm.run_validator(leader_result=forged) is False


def test_validator_rejects_an_extra_approval(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    direct_vm.mock_llm(PROMPT, _answers(("alice", "Approved: Alice Chen")))
    gate.check("v3", TWO_DOC)

    assert direct_vm.run_validator(leader_result={"signal": "OK:alice=Approved: Alice Chen,bob"}) is False


def test_validator_rejects_a_reading_reported_as_unusable(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    direct_vm.mock_llm(PROMPT, _answers(("alice", "Approved: Alice Chen")))
    gate.check("v4", ONE_DOC)

    assert direct_vm.run_validator(leader_result={"signal": "UNUSABLE"}) is False


def test_validator_rejects_a_broken_reading_reported_as_a_quorum(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    direct_vm.mock_llm(PROMPT, "not json at all")
    gate.check("v5", TWO_DOC)

    forged = {"signal": "OK:alice=Approved: Alice Chen|bob=Approved: Bob Ruiz"}
    assert direct_vm.run_validator(leader_result=forged) is False


def test_validator_rejects_a_payload_without_a_signal(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    direct_vm.mock_llm(PROMPT, _answers(("alice", "Approved: Alice Chen")))
    gate.check("v6", ONE_DOC)

    assert direct_vm.run_validator(leader_result={"signed": "alice"}) is False


def test_validator_rejects_a_leader_that_errored(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    direct_vm.mock_llm(PROMPT, _answers(("alice", "Approved: Alice Chen")))
    gate.check("v7", ONE_DOC)

    assert direct_vm.run_validator(leader_error=RuntimeError("boom")) is False


# ------------------------------------------------------------- the fixed roster
def test_the_roster_and_the_threshold_are_readable(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    assert gate.roster_of() == "alice,bob,carol"
    assert gate.roster_name_of("alice") == "Alice Chen"
    assert gate.roster_name_of("nobody") == ""
    assert gate.signer_count() == 3
    assert gate.needed() == 2
    assert gate.site_name() == "board"
    assert gate.config() == "board|3 signers|2 needed|0 cases"


def test_the_roster_has_no_write_path(direct_vm, direct_deploy):
    """A roster that can grow after the fact can be fitted to the document."""
    source = open("contracts/signoff_quorum.py", encoding="utf-8").read()
    for name in ("def add_signer", "def set_needed", "def remove_signer", "def set_roster"):
        assert name not in source
    gate = _gate(direct_deploy)
    assert gate.roster_of() == "alice,bob,carol"


def test_the_case_count_moves(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    direct_vm.mock_llm(PROMPT, '{"approvals": []}')
    gate.check("n1", TWO_DOC)
    gate.check("n2", ONE_DOC)
    assert gate.case_count() == 2
    assert gate.config() == "board|3 signers|2 needed|2 cases"


# --------------------------------------------------------------------- refusals
def test_an_unknown_case_fails_closed(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    assert gate.is_quorate("never-seen") is False
    assert gate.verdict_of("never-seen") == ""
    assert gate.signed_of("never-seen") == ""


def test_a_case_is_checked_once(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    direct_vm.mock_llm(PROMPT, '{"approvals": []}')
    gate.check("r1", TWO_DOC)
    with direct_vm.expect_revert("CASE_EXISTS"):
        gate.check("r1", TWO_DOC)


def test_a_bad_case_id_is_refused(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    with direct_vm.expect_revert("BAD_CASE_ID"):
        gate.check("bad id!", TWO_DOC)


def test_a_short_document_is_refused(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    with direct_vm.expect_revert("BAD_TEXT"):
        gate.check("r2", "too short")


def test_a_document_with_no_words_is_refused(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    with direct_vm.expect_revert("BAD_TEXT"):
        gate.check("r3", "............")


def test_a_page_of_sentences_that_prove_nothing_is_still_short(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    direct_vm.mock_llm(PROMPT, '{"approvals": []}')
    assert gate.check("r4", "The board met. The board will meet again.") == "SHORT"
    assert gate.missing_of("r4") == "alice,bob,carol"


# ------------------------------------------------------------------ construction
def test_a_short_site_label_is_refused(direct_vm, direct_deploy):
    with pytest.raises(Exception, match="BAD_SITE_LABEL"):
        direct_deploy("contracts/signoff_quorum.py", "ab", ROSTER, "2")


def test_a_roster_of_one_is_refused(direct_vm, direct_deploy):
    with pytest.raises(Exception, match="BAD_ROSTER"):
        direct_deploy("contracts/signoff_quorum.py", "board", "alice:Alice Chen", "1")


def test_a_roster_without_names_is_refused(direct_vm, direct_deploy):
    with pytest.raises(Exception, match="BAD_ROSTER"):
        direct_deploy("contracts/signoff_quorum.py", "board", "alice,bob", "1")


def test_a_duplicate_signer_code_is_refused(direct_vm, direct_deploy):
    with pytest.raises(Exception, match="ROSTER_DUP"):
        direct_deploy(
            "contracts/signoff_quorum.py", "board", "alice:Alice Chen,alice:Bob Ruiz", "1"
        )


def test_a_duplicate_person_is_refused(direct_vm, direct_deploy):
    with pytest.raises(Exception, match="ROSTER_DUP"):
        direct_deploy(
            "contracts/signoff_quorum.py", "board", "alice:Alice Chen,ali:Alice  Chen", "1"
        )


def test_a_signer_code_with_spaces_is_refused(direct_vm, direct_deploy):
    with pytest.raises(Exception, match="BAD_SIGNER"):
        direct_deploy(
            "contracts/signoff_quorum.py", "board", "a b:Alice Chen,bob:Bob Ruiz", "1"
        )


def test_a_threshold_above_the_roster_is_refused(direct_vm, direct_deploy):
    with pytest.raises(Exception, match="BAD_NEEDED"):
        direct_deploy("contracts/signoff_quorum.py", "board", ROSTER, "4")


def test_a_threshold_of_zero_is_refused(direct_vm, direct_deploy):
    with pytest.raises(Exception, match="BAD_NEEDED"):
        direct_deploy("contracts/signoff_quorum.py", "board", ROSTER, "0")


def test_a_threshold_that_is_not_a_number_is_refused(direct_vm, direct_deploy):
    with pytest.raises(Exception, match="BAD_NEEDED"):
        direct_deploy("contracts/signoff_quorum.py", "board", ROSTER, "two")

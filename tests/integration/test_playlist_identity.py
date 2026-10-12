import pytest
from mediaharvester.worker import selected_entry


def test_playlist_identity_exact_leaf():
    wanted={'id':'wanted','formats':[]}
    info={'id':'parent','entries':[{'id':'other'}, {'id':'nested','entries':[wanted]}]}
    assert selected_entry(info,'wanted') is wanted


@pytest.mark.parametrize('entries',[[{'id':'old'}],[{'id':'wanted'},{'id':'wanted'}]])
def test_playlist_identity_missing_or_ambiguous_rejected(entries):
    with pytest.raises(ValueError):selected_entry({'entries':entries},'wanted')


def test_last_of_100_playlist_entries_remains_selectable():
    entries=[{'id':str(index)} for index in range(100)]
    assert selected_entry({'entries':entries},'99') is entries[-1]

from forms import scan,formula_items,UREG
from prepare_quick import alternate


def test_large_number_round_trip_preserves_digits():
    for text in ['The value is 12000.', 'The value is 12,000.']:
        items=[x for x in scan(text,{}) if x['dimension']=='large_number']
        assert len(items)==1
        other=alternate(items[0],['comma','plain'])
        assert other.replace(',','')=='12000'


def test_percent_replacement_preserves_exact_value():
    items=[x for x in scan('The proportion is 5 percent.',{}) if x['dimension']=='percentage']
    assert alternate(items[0],['symbol','word'])=='5%'


def test_unit_replacement_does_not_convert_magnitude():
    item=next(x for x in scan('The mass is 2 kg.',{}) if x['dimension']=='unit_spelling')
    replacement=alternate(item,['plain_symbol','word_unit'])
    assert UREG.Unit(replacement)==UREG.kg


def test_formula_keeps_equation_sides_distinct():
    assert formula_items('F=m a')['canonical'] != formula_items('m a=F')['canonical']


def test_percentage_is_not_count_word():
    assert all(x['dimension']!='small_count' for x in scan('The probability is 5%.',{}))

"""Unit checks for smaller model-selected instrument actions, no scripted work."""
import json
from room_endogenous_activity_compact import (
    compact_request, decode, full_envelope, adapter, CHOICES, KINDS, SCHEMA,
)


def messages(owner='mara', records=None):
    ctx={'agent':owner,'identity':'Test unique model owner',
         'individual_current_goal':'Investigate changing sensor readings',
         'my_own_world_experiences':{
             'identity':owner,'own_witnessed_records':records or [],
             'shared_computed_evidence':[]}}
    return [{'role':'system','content':'Original instruction'},
            {'role':'user','content':json.dumps(ctx)}]


def test_wait_stays_a_valid_no_action():
    p=decode('{"action":"wait"}',messages())
    assert p=={'kind':'wait'}
    assert json.loads(full_envelope(p))['kind']=='wait'


def test_all_choices_map_to_explicit_real_instrument_operations():
    for choice,expected in KINDS.items():
        p=decode(json.dumps({'action':choice}),messages())
        assert p==expected
        assert json.loads(full_envelope(p))['kind']==expected['kind']
    assert set(SCHEMA['properties']['action']['enum'])==set(CHOICES)
    assert all('kind' in v for v in KINDS.values())


def test_one_schema_field_not_eight_dummy_fields():
    assert SCHEMA['required']==['action']
    assert SCHEMA['additionalProperties'] is False


def test_owner_share_latest_never_leaks_foreign_private_measurement():
    item={'id':'obs-'+'a'*24,'owner':'sarah','result':{'reported':7.4}}
    assert decode('{"action":"share_latest"}',messages('mara',[item]))=={'kind':'wait'}
    assert decode('{"action":"share_latest"}',messages('sarah',[item]))=={
        'kind':'share','source_id':item['id']}
    assert decode('{"action":"share_latest"}',messages('sarah',[]))=={'kind':'wait'}


def test_malformed_or_forbidden_choice_can_never_trigger_computation():
    for raw in ('I would measure oxygen.', '{invalid json',
                '{"action":"execute_shell"}',
                '{"action":"measure_oxygen","override":true}',
                '{"action":"measure-oxygen"}', None):
        assert decode(raw,messages())=={'kind':'wait'}


def test_private_identity_remains_user_data_not_system_control():
    out=compact_request(messages())
    assert out[0]['role']=='system'
    assert 'Test unique model owner' not in out[0]['content']
    assert 'Test unique model owner' in out[1]['content']
    assert out[1]['role']=='user'


def test_adapter_obeys_exact_model_action_once():
    seen=[]
    def model(prompt,timeout):
        seen.append((prompt,timeout))
        return '{"action":"calibrate_oxygen"}'
    inferred=adapter(model)
    payload=json.loads(inferred(messages('jules'),17.0))
    assert payload['kind']=='calibrate'
    assert payload['channel']=='oxygen'
    assert len(seen)==1 and seen[0][1]==17.0


if __name__=='__main__':
    tests=[v for k,v in sorted(globals().copy().items()) if k.startswith('test_') and callable(v)]
    for t in tests: t()
    print(f'PASS: {len(tests)} compact voluntary activity choice tests')

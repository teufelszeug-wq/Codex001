"""Quarantine raw recovered values; this is NOT an engine-input adapter.

Result archives mix entrant metadata with realized outcomes. These functions
extract an explicit allowlist, leave historical availability and canonical horse
identity unresolved, and cannot promote a record into PRE_AVAILABLE.
"""
import re
import unicodedata
from .contracts import digest


def text(value):
    return unicodedata.normalize('NFKC',str(value or '')).strip()


def number(value,low,high,integer=False):
    token=re.search(r'[+\-]?\d+(?:\.\d+)?',text(value).replace(',',''))
    if token is None:return None
    parsed=float(token.group())
    if not low<=parsed<=high or integer and not parsed.is_integer():return None
    return int(parsed) if integer else parsed


def counts(value):
    parts=re.findall(r'\d+',text(value))
    if len(parts)!=4:return None
    wins,seconds,thirds,unplaced=map(int,parts)
    return {'wins':wins,'seconds':seconds,'thirds':thirds,'unplaced':unplaced,
            'rides':wins+seconds+thirds+unplaced,'as_of_verified':False}


def candidate(race_id,horse_no,observations,source_ref,source_record,mode):
    if mode!='HISTORICAL_RECONSTRUCTION':raise ValueError('unknown availability requires historical reconstruction quarantine')
    if not isinstance(race_id,str) or not race_id.strip() or not isinstance(source_ref,str) or not source_ref.strip():raise ValueError('race and source identities required')
    if type(horse_no) is not int or not 1<=horse_no<=24:raise ValueError('explicit valid horse number required')
    out={'schema':'prism.recovered-observations-hold/v1','mode':mode,'race_id':race_id,
         'horse_identity':{'horse_no':horse_no,'horse_id':None,'resolution_status':'UNRESOLVED_CANONICAL_ID'},
         'observations':observations,
         'source':{'source_ref':source_ref,'source_record_hash':digest(source_record),'available_at':None,
                   'temporal_class':'UNKNOWN_TIMESTAMP','authenticity_verified':False},
         'engine_ready':False,'pre_available_certified':False,'trained_model':False,
         'release_requirements':['Canonical horse and rider identity resolution.',
                                 'Historical publication timestamp and source provenance verification.',
                                 'As-of audit for rider aggregates; no current-race outcomes in PRE.',
                                 'Separate condition assessment or validated model; do not invent a score.']}
    out['candidate_hash']=digest(out);return out


def extract_nar_candidate(record,race_id,source_ref,mode='HISTORICAL_RECONSTRUCTION'):
    if not isinstance(record,dict):raise ValueError('raw NAR record required')
    # No rank/time/sectional/popularity/return fields are ever copied.
    observations={'frame_no':number(record.get('枠番'),1,8,True),
                  'carried_weight_kg':number(record.get('負担重量'),1,2000),
                  'body_weight_kg':number(record.get('馬体重'),100,2000),
                  'body_weight_change_kg':number(record.get('馬体重増減'),-1000,1000,True),
                  'jockey_name':text(record.get('騎手名')) or None,
                  'jockey_counts_unverified':counts(record.get('騎手成績'))}
    return candidate(race_id,number(record.get('馬番'),1,24,True),observations,source_ref,record,mode)


def extract_jra_candidate(cells,race_id,source_ref,frame_image_alt='',mode='HISTORICAL_RECONSTRUCTION'):
    if not isinstance(cells,dict):raise ValueError('raw JRA cell text mapping required')
    body=text(cells.get('h_weight'));change=re.search(r'\(([+\-]?\d+)\)',body)
    observations={'frame_no':number(cells.get('waku') or frame_image_alt,1,8,True),
                  'carried_weight_kg':number(cells.get('weight'),1,2000),
                  'body_weight_kg':number(body,100,2000),
                  'body_weight_change_kg':int(change.group(1)) if change else None,
                  'jockey_name':text(cells.get('jockey')) or None,
                  'jockey_counts_unverified':None}
    return candidate(race_id,number(cells.get('num'),1,24,True),observations,source_ref,
                     {'cells':cells,'frame_image_alt':frame_image_alt},mode)

from arknights_merch_analytics.public_expansion import (
    money, normalize_products, operator_metadata, latest_union, skland_entities, classify_product,
)


def product(pid=1, title='Arknights | Acrylic Standee'):
    return {'id':pid,'title':title,'handle':'test-'+str(pid),'product_type':'Acrylic Standee',
            'tags':['Arknights'],'options':[{'name':'Character'}],
            'variants':[{'id':9,'title':'Amiya','sku':'AMIYA','price':'18.00',
                         'compare_at_price':None,'available':True}]}


def test_store_qualified_ids_do_not_merge_cross_channel_products():
    a,av=normalize_products({'products':[product()]},'yostar_us','2026-09-12')
    b,bv=normalize_products({'products':[product()]},'gryphline_global','2026-09-12')
    assert a[0]['product_key']!=b[0]['product_key']
    assert av[0]['variant_key']!=bv[0]['variant_key']
    assert a[0]['currency']=='USD'


def test_endfield_and_unrelated_products_are_not_accepted():
    unrelated=product(3,'Azur Lane');unrelated['tags']=['Azur Lane']
    rows,_=normalize_products({'products':[product(),product(2,'Arknights: Endfield'),unrelated]},'yostar_us','x')
    assert len(rows)==1


def test_unknown_price_and_availability_not_converted_to_zero_or_false():
    p=product();p['variants'][0].update(price=None,available=None)
    rows,variants=normalize_products({'products':[p]},'yostar_us','x')
    assert variants[0]['price'] is None and variants[0]['available'] is None
    assert rows[0]['price_min'] is None and rows[0]['unknown_availability_count']==1
    assert money('NaN') is None and money('-3') is None and money('bad') is None
    assert money('0')==0


def test_repeat_product_and_variant_rows_do_not_inflate_identity_count():
    p=product();p['variants'].append(dict(p['variants'][0]))
    rows,variants=normalize_products({'products':[p,p]},'yostar_us','x')
    assert len(rows)==len(variants)==rows[0]['variant_count']==1
    assert rows[0]['available_variant_count']==1


def test_product_category_avoids_embedded_words_and_generic_box():
    assert classify_product('Arknights Camping Tableware Set','Camping Tableware Set')=='桌面与生活用品'
    assert classify_product('Arknights Papercut Light Box','Papercut Light Box')=='桌面与生活用品'
    assert classify_product('Arknights Metal Pins','')=='徽章'
    assert classify_product('Arknights','Bottles')=='杯具'
    assert classify_product('Arknights Dango Plushie','Plushie Key Charm')=='毛绒玩偶'
    assert classify_product('Arknights Painted Glass Charm','Key Charm（非亚克力）')=='挂件'


def test_operator_reference_excludes_summons_and_unobtainable():
    attrs={'name':'Amiya','isNotObtainable':False}
    rows=operator_metadata({'char_1':attrs,'token_1':attrs,'char_2':{'isNotObtainable':True}},'url','sha','time')
    assert [r['operator_id'] for r in rows]==['char_1']
    assert rows[0]['source_commit']=='sha'


def test_repeat_snapshots_update_metrics_without_creating_new_entities():
    result=latest_union([{'id':'1','view':10,'title':'a'}],[{'id':'1','view':11},{'id':'2','view':4}],'id')
    assert len(result)==2 and result[0]['view']==11 and result[0]['title']=='a'


def test_search_observations_are_filtered_and_deduplicated():
    base={'item_id':'1','title':'阿米娅开箱','query':'开箱','query_kind':'merch_topic','query_title_match':True}
    result=skland_entities([base,{**base,'query':'阿米娅','query_kind':'operator'},
                            {**base,'item_id':'2','query_title_match':False}])
    assert len(result)==1
    assert result[0]['query_kinds']=='merch_topic,operator'
    assert '开箱' in result[0]['matched_queries']

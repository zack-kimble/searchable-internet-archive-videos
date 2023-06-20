from internetarchive import get_item, download, get_session

s = get_session()
s.mount_http_adapter()
search_results = s.search_items('Knoxville Community Media')
search_results = s.search_items('creator:(Knoxville Community Media) AND subject:(City Council)')

search_items = [x for x in search_results]
item = get_item(search_items[0]['identifier'])
item.download(formats='h.264')
for format in preferred_formats():
    result = item.download(format=format)
    if len(result) > 0:
        break


item = get_item('nasa')
kpm = get_item('Knoxville Community Media')
x==0
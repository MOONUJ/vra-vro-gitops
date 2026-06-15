import ssl
import time
import json
import os
import base64
import http.client
from urllib.parse import urlparse, quote
def save_binary_to_file(binary_data, filename=None):
    """
    바이너리 데이터를 파일로 저장
    """
    temp_dir = "/usr/lib/vco/app-server/temp/"
    
    # 디렉토리 생성 (없으면)
    os.makedirs(temp_dir, exist_ok=True)
    
    # 파일명 생성
    if not filename:
        filename = f"download_{uuid.uuid4().hex[:8]}.bin"
    
    save_path = os.path.join(temp_dir, filename)
    
    # 파일 저장
    with open(save_path, 'wb') as f:
        f.write(binary_data)
    
    return {
        'success': True,
        'file_path': save_path,
        'file_size': len(binary_data),
        'filename': filename
    }

def handler(context, inputs):
    url = inputs['url']
    parsed_url = urlparse(url)
    #proto, path = url.split("://")
    #proto = proto.lower()
    #host = path.split("/")[0]
    #path = path.replace(host, "", 1)
    proto = parsed_url.scheme.lower()
    host = parsed_url.netloc
    path = parsed_url.path
    if parsed_url.query:
        encoded_query = quote(parsed_url.query, safe="=&:")
        path += '?' + encoded_query
    method = inputs['method'].upper()
    headers = inputs['headers']

    if proto == "http": conn = http.client.HTTPConnection(host)
    elif proto == "https": conn = http.client.HTTPSConnection(host, context=ssl._create_unverified_context())
    else: raise Exception('Error [execPyCurl] : un-supported protocol')

    if method in ['POST', 'PUT', 'PATCH']:
        body = inputs['data']
        if not body: body = ''
        conn.request(method, path, body=body, headers=headers)
    else: conn.request(method, path, headers=headers)
    res = conn.getresponse()
    print('pyURL {}: {} >> {}'.format(method, url, res.status))
    if res.status >= 400:
        if res.status == 429:
            time.sleep(1)
            res = handler(context, inputs)
        else: raise Exception('Error [execPyCurl] : {}'.format(res.read().decode("utf-8")))
    response_data = res.read()
    
    content_type = res.getheader('content-type', '').lower()
    if any(binary_type in content_type for binary_type in ['zip', 'octet-stream', 'image/', 'video/', 'audio/']):
        # 바이너리 데이터는 Base64로 인코딩
        return base64.b64encode(response_data).decode('ascii')
    else:
        # 텍스트 데이터는 기존 방식
        try:
            return response_data.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return response_data.decode("cp949")
            except UnicodeDecodeError:
                return response_data.decode("utf-8", errors="replace")
    
    
#    return res.read().decode("utf-8", errors="replace")
import requests
from loguru import logger
from datetime import datetime, timedelta
import urllib.parse
import hashlib
import json
import time
import base64

basic_headers = {'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/99.0.4844.84 "
                               "Safari/537.36 "
                               "OPR/85.0.4341.60 (Edition Yx 05)",
                 "X-Requested-With": "XMLHttpRequest",
                 "Accept": "application/json, text/javascript, */*; q=0.01",
                 "Accept-Encoding": "gzip, deflate",
                 "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                 "dnt": "1",
                 "sec-gpc": "1"
                 }


def load_settings():
    with open("settings.json", "r") as settings_file:
        return json.load(settings_file)


def base64_encode(string: str) -> str:
    return str(base64.b64encode(bytes(string, 'utf-8')), encoding='utf-8')


def login(password):
    response = requests.post(f"http://{settings['zte_ip']}/goform/goform_set_cmd_process",
                           data={'isTest': 'false',
                                 'goformId': 'LOGIN',
                                 'password': base64_encode(password)},
                           headers=basic_headers | {
                               "Origin": f"http://{settings['zte_ip']}",
                               "Referer": f"http://{settings['zte_ip']}/index.html"})
    if response.json()['result'] != "0":
        raise Exception("Auth Error")
    logger.debug(f"Auth: {response}")
    # return 'stok' cookie -> important for folowing work
    return {"stok": response.cookies.get("stok")}


def logoff(cookies, AD):
    url = f"http://{settings['zte_ip']}/goform/goform_set_cmd_process"
    referer = f"http://{settings['zte_ip']}/index.html"
    
    data = {
        "isTest": "false",
        "goformId": "LOGOFF",
        "AD": AD
    }
    headers = {
        "Referer": referer
    }

    response = requests.post(url, data=data, headers=headers, cookies=cookies)
    return response


# get important data to create a request hash (AD)
def get_data_ver(cookie):
    response = requests.get(f"http://{settings['zte_ip']}/goform/goform_get_cmd_process?"
                          "isTest=false&"
                          "cmd=Language,cr_version,wa_inner_version,RD&multi_data=1",
                          headers=basic_headers | {"Referer": f"http://{settings['zte_ip']}/index.html"},
                          cookies=cookie)
    logger.debug(f"Get data RD: {response}")
    return response


def send_sms(cookies, uc_number, uc_message, AD):
    url = f"http://{settings['zte_ip']}/goform/goform_set_cmd_process"
    referer = f"http://{settings['zte_ip']}/index.html"
    sms_time = format_datetime()

    data = {
        "isTest": "false",
        "goformId": "SEND_SMS",
        "notCallback": "true",
        "Number": uc_number,
        "sms_time": sms_time,
        "MessageBody": uc_message,
        "ID": "-1",
        "encode_type": "UNICODE",
        "AD": AD
    }

    headers = {
        "Referer": referer
    }

    response = requests.post(url, data=data, headers=headers, cookies=cookies)

    logger.debug(f"SEND SMS: {response}")
    if response.status_code == 200:
        result = response.json().get("result")
        if result == "success":
            return True
        else:
            print("ERROR: response was not 'success'.")
    else:
        print("ERROR: Status-Code", response.status_code)

    return response



def format_datetime():
    # get UTC time
    now = datetime.utcnow()

    # adjust time (+2.0 hours)
    adjusted_now = now + timedelta(hours=2, minutes=0)

    # get formated string for modem
    formatted_datetime = adjusted_now.strftime("%Y;%m;%d;%H;%M;%S;%z")

    return formatted_datetime



def generate_AD(wa_version, cr_version, rd_hash):
    # Hash wa_version + cr_version using MD5
    hashed_concatenation = hashlib.md5((wa_version + cr_version).encode()).hexdigest()
    
    # Concatenate the first MD5 hash with rd_hash
    concatenated_string = hashed_concatenation + rd_hash
    
    # Hash the concatenated string using MD5 again
    AD = hashlib.md5(concatenated_string.encode()).hexdigest()

    return AD


def prepare_sms_text(unicode_str):
    # code Text in UTF-16 and hex
    encoded_text = unicode_str.encode('utf-16-be').hex().upper()
    return encoded_text



if __name__ == '__main__':
    settings = load_settings()
    logger.debug("Settings loaded")
    cookies = login(settings["password"])
    logger.debug(f"Cookies: {cookies}")
    info_dict = {}
    info_dict.update(get_data_ver(cookies).json())
    logger.debug(info_dict)
    logger.info(f"Language: {info_dict['Language']}")
    logger.info(f"cr_version: {info_dict['cr_version']}")
    logger.info(f"wa_inner_version: {info_dict['wa_inner_version']}")
    logger.info(f"RD: {info_dict['RD']}")


    AD = generate_AD(info_dict['wa_inner_version'], info_dict['cr_version'], info_dict['RD'])
    print("AD:", AD)


    unicode_str = "Hello, this is a test message: 你好世界!"

    phone_number = "0123456789"

    send_sms(cookies, phone_number, prepare_sms_text(unicode_str), AD)
    logoff(cookies,AD)


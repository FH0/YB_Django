import asyncio
import requests
import re
import base64
import time
from django.http import HttpResponse
from aiohttp import ClientSession, FormData
from django.shortcuts import render
from django.views.decorators import csrf
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
import datetime
import ssl
import certifi
import urllib
import json
import string
import random
import sys

timestring = ''  # 当前时间的字符串格式
data_token = ''  # 用于发布博文
my_id = ''  # 我的 id
puid = ''  # 学校的id
group_id = ''  # 组的id


# 登录状态接口
def is_login(request):
    cookies = get_cookies(request)

    r = requests.post('https://www.yiban.cn/ajax/my/getLogin',
                      cookies=cookies).json()
    return JsonResponse({'isLogin': r['data']['isLogin']}, safe=False)


# 验证码接口
def captcha(request):
    if 'key' in request.GET:
        cookies = get_cookies(request)
        r = requests.get("https://www.yiban.cn/captcha/index?" +
                         str(int(time.time())), cookies=cookies)
        return HttpResponse(r.content, content_type="image/jpeg")


# 网薪和经验接口
def wangxin_jingyan(request):
    cookies = get_cookies(request)
    my_id = requests.post('https://www.yiban.cn/ajax/my/getLogin',
                          cookies=cookies).json()['data']['user']['id']
    res = requests.get(
        'https://www.yiban.cn/user/index/index/user_id/' + my_id, cookies=cookies).text
    wangxin = re.findall(r'user-money">(.*?)</span', res, re.S)[0]
    jingyan = re.findall(r'经验：</label>(.*?)</p>', res, re.S)[0]
    return HttpResponse("网薪:"+wangxin+"&nbsp&nbsp经验:"+jingyan)


# 登录接口
@csrf_exempt
def login(request):
    cookies = get_cookies(request)

    # 传入的 json 是二进制格式，需要重新加载
    r_json = json.loads(request.body)

    # 获取 cookies data_keys data_keys_time encrypt_password 用于 doLoginAjax
    login_response = requests.get(
        'https://www.yiban.cn/login', cookies=cookies)
    cookies.update(login_response.cookies.get_dict())
    data_keys = re.findall(r'data-keys=\'(.*?)\'',
                           login_response.text, re.S)[0]
    data_keys_time = re.findall(
        r'data-keys-time=\'(.*?)\'', login_response.text, re.S)[0]
    encrypt_password = get_crypt_password(
        data_keys, r_json['password'])

    # post 易班登录接口
    r = requests.post('https://www.yiban.cn/login/doLoginAjax', {
        'account': r_json['account'], 'password': encrypt_password, 'captcha': r_json['captcha'], 'keysTime': data_keys_time}, cookies=cookies, allow_redirects=False)
    cookies.update(r.cookies.get_dict())
    response = JsonResponse(
        {'message': r.json()['message'], 'code': r.json()['code']}, safe=False)

    # 保存一些信息到cookies
    lease = 30 * 24 * 60 * 60  # 30 days in seconds
    end = time.gmtime(time.time() + lease)
    expires = time.strftime("%a, %d-%b-%Y %T GMT", end)
    for i in cookies:
        response.set_cookie(i, cookies[i], expires=expires)

    return response


# 刷取接口
def rush_yb(request):
    cookies = get_cookies(request)

    # 填充全局变量
    josn = requests.post('https://www.yiban.cn/ajax/my/getLogin',
                         cookies=cookies).json()
    global data_token, my_id, puid, group_id
    data_token = josn['data']['user']['token']
    my_id = josn['data']['user']['id']
    r = requests.get('https://www.yiban.cn/my/group', cookies=cookies).text
    group_id = re.findall(r'data-groupid="([0-9]+)', r, re.S)[0]
    puid = re.findall(r'data-puid="([0-9]+)', r, re.S)[0]

    # 格式化时间
    global timestring
    timestring = '{0:%Y-%m-%d %H:%M:%S}'.format(datetime.datetime.now())

    # 刷取, aiohttp异步
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(tasks_list(cookies))
    loop.close()

    return HttpResponse("执行完毕")


# 任务清单
async def tasks_list(cookies):
    tasks = []
    sslcontext = ssl.create_default_context(cafile=certifi.where())
    session = ClientSession(cookies=cookies)

    tasks.append(asyncio.ensure_future(
        group_article(session, sslcontext)))
    tasks.append(asyncio.ensure_future(dongtai(session, sslcontext)))
    tasks.append(asyncio.ensure_future(
        yimiaomiao(session, sslcontext, cookies)))
    tasks.append(asyncio.ensure_future(
        sign_in_question(session, sslcontext)))
    tasks.append(asyncio.ensure_future(post_blog(session, sslcontext)))
    tasks.append(asyncio.ensure_future(comment_vote(session, sslcontext)))
    tasks.append(asyncio.ensure_future(database(session, sslcontext)))

    await asyncio.gather(*tasks)
    await session.close()


# 群组文章 网薪经验+10
async def group_article(session, sslcontext):

    async def fetch(channel_id, article_id):
        try:
            form_json = {
                'channel_id': channel_id,
                'puid': puid,
                'article_id': article_id,
                'content': timestring,
                'reply_id': '0',
                'syncFeed': '0',
                'isAnonymous': '0'
            }
            response = await session.post("https://www.yiban.cn/forum/reply/addAjax", data=form_json, ssl_context=sslcontext)
            await response.read()
        except Exception as e:
            print(str(sys._getframe().f_lineno) + ': ' + str(e))

    try:
        r = await session.get('https://www.yiban.cn/Org/orglistShow/puid/'+puid+'/group_id/'+group_id+'/type/forum', ssl_context=sslcontext)
        r = await r.text()
        channel_id = re.findall(r'channel_id: \'([0-9]+)', r, re.S)[0]
        form_json = {
            'channel_id': channel_id,
            'puid': puid,
            'page': '1',
            'size': '10',
            'orderby': 'updateTime',
            'Sections_id': '-1',
            'need_notice': '0',
            'group_id': group_id,
            'my': '0'
        }
        r = await session.post("https://www.yiban.cn/forum/article/listAjax", data=form_json, ssl_context=sslcontext)
        r_json = json.loads(await r.read())
        tasks = []
        for i in range(10):
            tasks.append(asyncio.ensure_future(
                fetch(channel_id, r_json['data']['list'][i]['id'])))
        tasks.append(asyncio.ensure_future(
            post_topic(session, sslcontext)))  # 获得群组文章列表后才发布话题
        await asyncio.gather(*tasks)
    except Exception as e:
        print(str(sys._getframe().f_lineno) + ': ' + str(e))


# 发布动态 经验网薪+2
async def dongtai(session, sslcontext):
    try:
        async with session.post("https://www.yiban.cn/feed/add", data={'content': timestring, 'privacy': '3', 'dom': '.js-submit'}, ssl=sslcontext) as response:
            await response.read()
    except Exception as e:
        print(str(sys._getframe().f_lineno) + ': ' + str(e))


# 易瞄瞄 经验网薪+2
async def yimiaomiao(session, sslcontext, cookies):
    try:
        async with session.post("https://ymm.yiban.cn/article/index/add", data={"title": timestring, "content": timestring, "kind": '1', "agree": 'true'}, headers={'loginToken': cookies['yiban_user_token']}, ssl=sslcontext) as response:
            await response.read()
    except Exception as e:
        print(str(sys._getframe().f_lineno) + ': ' + str(e))


# 回答签到问题 经验网薪+1
async def sign_in_question(session, sslcontext):
    try:
        async with session.post("https://www.yiban.cn/ajax/checkin/answer", data={'optionid[]': '17131', 'input': ''}, ssl=sslcontext) as response:
            await response.read()
    except Exception as e:
        print(str(sys._getframe().f_lineno) + ': ' + str(e))


# 发布话题 网薪经验+10
async def post_topic(session, sslcontext):

    async def fetch():
        async with session.post('https://www.yiban.cn/forum/article/addAjax', data={
            'puid': puid,
            'pubArea': group_id,
            'title': timestring,
            'content': timestring,
            'isNotice': 'false',
            'dom': '.js-submit'
        }, ssl=sslcontext) as response:
            await response.read()

    try:
        tasks = []
        for i in range(2):
            tasks.append(asyncio.ensure_future(fetch()))
        await asyncio.gather(*tasks)
    except Exception as e:
        print(str(sys._getframe().f_lineno) + ': ' + str(e))


# 发布博文 网薪经验+10
async def post_blog(session, sslcontext):

    async def fetch():
        async with session.post('https://www.yiban.cn/blog/blog/addblog', data={
            'title': timestring,
            'content': timestring,
            'range': '2',
            'type': '1',
                    'token': data_token,
                    'ymm': '0',
                    'dom': '.js-submit'
        }, ssl=sslcontext) as response:
            await response.read()

    try:
        tasks = []
        for i in range(5):
            tasks.append(asyncio.ensure_future(
                fetch()))
        await asyncio.gather(*tasks)
        await like_blog(session, sslcontext)  # 发布之后才能点赞
    except Exception as e:
        print(str(sys._getframe().f_lineno) + ': ' + str(e))


# 点赞博文 网薪经验+5
async def like_blog(session, sslcontext):

    async def fetch(blogid):
        try:
            async with session.get("https://www.yiban.cn/blog/blog/addlike?uid=" +
                                   my_id +
                                   "&blogid=" +
                                   blogid, ssl=sslcontext) as response:
                await response.read()
        except Exception as e:
            print(str(sys._getframe().f_lineno) + ': ' + str(e))

    try:
        r = await session.get('https://www.yiban.cn/blog/blog/getBlogList?page=1&size=10&uid='+my_id, ssl_context=sslcontext)
        r = json.loads(await r.text())
        tasks = []
        for i in range(5):
            tasks.append(asyncio.ensure_future(
                fetch(r['data']['list'][i]['id'])))
        await asyncio.gather(*tasks)
    except Exception as e:
        print(str(sys._getframe().f_lineno) + ': ' + str(e))


# 评论投票 网薪经验+10
async def comment_vote(session, sslcontext):

    async def fetch(vote_id, actor_id):
        try:
            form_json = {
                'vote_id': vote_id,
                'uid': actor_id,
                'puid': puid,
                'pagetype': '1',
                'group_id': group_id,
                'actor_id': my_id,
                'token': '',
                'isSchoolVerify': '1',
                'isLogin': '1',
                'isOrganization': '0',
                'ispublic': '0'
            }
            async with session.post(
                    'https://www.yiban.cn/vote/vote/getVoteDetail', data=form_json, ssl=sslcontext) as response:
                r_json = json.loads(await response.read())
                form_json = {
                    'mountid': r_json['data']['vote_list']['Mount_id'],
                    'msg': '1',
                    'group_id': group_id,
                    'actor_id': my_id,
                    'vote_id': vote_id,
                    'author_id': actor_id,
                    'puid': puid,
                    'reply_comment_id': '0',
                    'reply_user_id': '0'
                }
                async with session.post(
                        "https://www.yiban.cn/vote/vote/addComment", data=form_json, ssl=sslcontext) as response:
                    await response.read()
        except Exception as e:
            print(str(sys._getframe().f_lineno) + ': ' + str(e))

    try:
        page_count = 1
        reply_count = 0
        tasks = []
        while page_count <= 15 and reply_count < 10:
            r = await session.get('https://www.yiban.cn/newgroup/showMorePub/puid/'+puid+'/group_id/'+group_id+'/type/3/page/' +
                                  str(page_count), ssl_context=sslcontext)
            r = await r.text()
            vote_id = re.findall(r'vote_id/([0-9]+)', r, re.S)
            vote_id = list(dict.fromkeys(vote_id))
            for i in range(len(vote_id)):
                actor_id = re.findall(
                    r'vote_id/'+vote_id[i]+'/puid/'+puid+'/group_id/'+group_id+'/actor_id/([0-9]+)', r, re.S)[0]
                if actor_id != my_id:
                    tasks.append(asyncio.ensure_future(
                        fetch(vote_id[i], actor_id)))
                    reply_count += 1
            page_count += 1
        await asyncio.gather(*tasks)
        await multi_vote(session, sslcontext)  # 评论完其他人的再发布自己的
    except Exception as e:
        print(str(sys._getframe().f_lineno) + ': ' + str(e))


# 发布投票然后点赞、投票 网薪经验+20
async def multi_vote(session, sslcontext):

    async def fetch():
        try:
            form_json = {
                'puid': puid,
                'scope_ids': group_id,
                'title': timestring,
                'subjectTxt': timestring,
                'subjectPic': '',
                'options_num': '2',
                'scopeMin': '1',
                'scopeMax': '1',
                'minimum': '1',
                'voteValue': '2020-04-08+09%3A48',
                'voteKey': '2',
                'public_type': '0',
                'isAnonymous': '2',
                'voteIsCaptcha': '0',
                'istop': '1',
                'sysnotice': '2',
                'isshare': '1',
                'rsa': '1',
                'dom': '.js-submit',
                'group_id': group_id,
                'subjectTxt_1': timestring,
                'subjectTxt_2': timestring
            }
            async with session.post(
                    "https://www.yiban.cn/vote/vote/add", data=form_json, ssl=sslcontext) as response:
                r_json = json.loads(await response.read())
                form_json = {
                    'puid': puid,
                    'group_id': group_id,
                    'vote_id': r_json['data']['lastInsetId'],
                    'actor_id': my_id,
                    'voptions_id': '227443671',
                    'minimum': '1',
                    'scopeMax': '1'
                }
                async with session.post("https://www.yiban.cn/vote/vote/act", data=form_json, ssl=sslcontext) as response:
                    await response.read()
                form_json = {
                    'puid': puid,
                    'group_id': group_id,
                    'vote_id': r_json['data']['lastInsetId'],
                    'actor_id': my_id,
                    'flag': '1'
                }
                async with session.post("https://www.yiban.cn/vote/vote/editLove", data=form_json, ssl=sslcontext) as response:
                    await response.read()
        except Exception as e:
            print(str(sys._getframe().f_lineno) + ': ' + str(e))

    tasks = []
    for i in range(5):
        tasks.append(asyncio.ensure_future(fetch()))
    await asyncio.gather(*tasks)


# 资料库 经验网薪+20
async def database(session, sslcontext):

    async def fetch(i):
        try:
            ranstr = ''.join(random.sample(
                string.ascii_letters + string.digits, 16))
            params = {
                'path': ranstr + '.txt',
                'size': '11',
                'type': ''
            }
            async with session.post(
                    "https://www.yiban.cn/File/ajax/uploadBigTask", params=params, ssl=sslcontext) as response:
                token = json.loads(await response.read())['data']['token']
                params = {
                    'path': ranstr + '.txt',
                    'token': token,
                    'num': '0',
                    'offset': '0',
                    'limit': '11'
                }
                data = FormData()
                data.add_field('upload', 'hello world', filename=ranstr +
                               '.txt', content_type='application/octet-stream')
                async with session.post(
                        "https://www.yiban.cn/File/ajax/uploadBigBlock", data=data, params=params, ssl=sslcontext) as response:
                    await response.read()
                    params = {
                        'path': ranstr + '.txt',
                        'size': '11',
                        'type': ''
                    }
                    async with session.post(
                            "https://www.yiban.cn/File/ajax/uploadBigTask", params=params, ssl=sslcontext) as response:
                        path = json.loads(await response.read())['data']['done_fileinfo']['name']
                        params = {
                            'path': path,
                            'perm': 'P',
                            'group': 'null'
                        }
                        async with session.post(
                                "https://www.yiban.cn/File/ajax/shareAdd", params=params, ssl=sslcontext) as response:
                            await response.read()
        except Exception as e:
            print(str(sys._getframe().f_lineno) + ': ' + str(e))

    tasks = []
    for i in range(10):
        tasks.append(asyncio.ensure_future(fetch(i)))
    await asyncio.gather(*tasks)


# 返回过滤后的 cookies
def get_cookies(request):
    # 传入的 json 是二进制格式，需要重新加载
    try:
        r_json = json.loads(request.body)
    except:
        r_json = {}

    if request.method == 'POST' and (not 'new_account' in r_json or r_json['new_account'] == '0'):
        return {}
    else:
        return request.COOKIES


# 用于报错输出
def red_print(str):
    print('\033[31m'+str+'\033[0m')


# 下面两个函数从https://github.com/SadTomlzr/yiban_Automation_tool/blob/f40ec98d319b32f9ccccba77f2313459b9b19628/EGPA_script_random_num.py复制而来
def get_crypt_password(private_key, password):
    rsa = RSA.importKey(private_key)
    cipher = PKCS1_v1_5.new(rsa)
    ciphertext = encrypt(password, cipher)
    return ciphertext


def encrypt(msg, cipher):
    ciphertext = cipher.encrypt(msg.encode('utf8'))
    return base64.b64encode(ciphertext).decode('ascii')

import os
from re import compile
import ssl
import traceback
from typing import Any
from datetime import datetime, timedelta

import sys
import asyncio
import requests
from requests.adapters import HTTPAdapter

from . import systems
from .data import Constants
from .systems import Account
from .authclient import AuthClient

syst = systems.system()

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
elif sys.platform == 'linux':
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
elif sys.platform == 'darwin':
    asyncio.set_event_loop_policy(asyncio.SelectorEventLoopPolicy())

class SSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *a: Any, **k: Any) -> None:
        c = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        c.set_ciphers(':'.join(Constants.CIPHERS))
        k['ssl_context'] = c
        return super(SSLAdapter, self).init_poolmanager(*a, **k)


class Auth():
    def __init__(self, isDebug : bool = False) -> None:
        self.isDebug = bool(isDebug)
        path = str(os.getcwd())
        self.useragent = Constants.RIOTCLIENT
        self.parentpath = str(os.path.abspath(os.path.join(path, os.pardir)))

    async def auth(self, logpass : str = None, username : str =None, password : str =None, proxy=None) -> Account:
        account = Account()
        try:
            account.logpass = str(logpass)
            session = requests.Session()
            ac = AuthClient()
            authsession = await ac.createSession()
            if username is None:
                username = logpass.split(':')[0].strip()
                password = logpass.split(':')[1].strip()

            try:
                # R1
                headers = {
                    "Accept-Encoding": "deflate, gzip, zstd",
                    "user-agent": "dsadasdasdasds",
                    "Cache-Control": "no-cache",
                    "Accept": "application/json",
                }
                body = {
                    "acr_values": "",
                    "claims": "",
                    "client_id": "riot-client",
                    "code_challenge": "",
                    "code_challenge_method": "",
                    "nonce": "dsadasdasdasdasd",
                    "redirect_uri": "http://localhost/redirect",
                    "response_type": "token id_token",
                    "scope": "openid link ban lol_region account",
                }
                async with authsession.post(
                    Constants.AUTH_URL,
                    json=body,
                    headers=headers,
                    proxy = proxy["http"] if proxy is not None else None
                ) as r:
                    pass
                    debugvalue_raw = await r.text()
                    #input(debugvalue_raw)

                # R2
                data = dict({
                    'type': str('auth'),
                    'username': str(username),
                    'password': str(password)
                })
                async with authsession.put(
                    Constants.AUTH_URL,
                    json=data,
                    headers=headers,
                    proxy = proxy["http"] if proxy is not None else None
                ) as r:
                    try:
                        data = await r.json()
                        #input(data)
                    except Exception as e:
                        #input(e)
                        account.code = 6
                        await authsession.close()
                        return account
                    r2text = str(await r.text())        
                await authsession.close()
            except Exception as e:
                #input(traceback.format_exc())
                await authsession.close()
                if self.isDebug:
                    input(traceback.format_exc())
                account.code = 6
                return account
            if "access_token" in r2text:
                pattern = compile(
                    'access_token=((?:[a-zA-Z]|\d|\.|-|_)*).*id_token=((?:[a-zA-Z]|\d|\.|-|_)*).*expires_in=(\d*)')
                data = pattern.findall(
                    data['response']['parameters']['uri'])[0]
                token = data[0]
                token_id = data[1]
            elif 'invalid_session_id' in r2text:
                account.code = 6
                return account
            elif "auth_failure" in r2text:
                account.code = 3
                return account
            elif 'rate_limited' in r2text:
                account.code = 1
                return account
            elif 'multifactor' in r2text:
                account.code = 3
                return account
            elif 'cloudflare' in r2text:
                account.code = 5
                return account
            else:
                account.code = 3
                return account

            headers = dict({
                'User-Agent': str(f'RiotClient/{self.useragent} %s (Windows;10;;Professional, x64)'),
                'Authorization': str(f'Bearer {token}'),
            })
            try:
                with session.post(Constants.ENTITLEMENT_URL, headers=headers, json={}, proxies=proxy) as r:
                    entitlement = r.json()['entitlements_token']
                r = session.post(Constants.USERINFO_URL,
                                 headers=headers, json={}, proxies=proxy)
            except Exception as e:
                account.code = 6
                return account
            # print(r.text)
            # input()
            # input(r.text)
            data = r.json()
            # print(data)
            # input()
            gamename = data['acct']['game_name']
            tagline = data['acct']['tag_line']
            register_date = data['acct']['created_at']
            registerdatepatched = datetime.fromtimestamp(
                int(register_date) / 1000.0)
            puuid = data['sub']
            try:
                #input(data)
                data2 = data['ban']
                # input(data2)
                data3 = data2['restrictions']
                # input(data3)
                if len(data3) == 0:
                    banuntil = None
                else:
                    typebanned = data3[0]['type']
                    if typebanned == "PERMANENT_BAN" or typebanned == 'PERMA_BAN':
                        account.code = int(4)
                        banuntil = None
                    elif 'PERMANENT_BAN' in str(data3) or 'PERMA_BAN' in str(data3):
                        account.code = int(4)
                        banuntil = None
                    elif typebanned == 'TIME_BAN' or typebanned == 'LEGACY_BAN':
                        expire = data3[0]['dat']['expirationMillis']
                        expirepatched = datetime.fromtimestamp(
                            int(expire) / 1000.0)
                        if expirepatched > datetime.now() + timedelta(days=365 * 20):
                            account.code = 4
                        banuntil = expirepatched
                    else:
                        banuntil = None
                        pass
            except Exception as e:
                # print(Exception)
                #input(e)
                banuntil = None
                pass
            try:
                # headers= dict({
                #    'Authorization': f'Bearer {token}',
                #    'Content-Type': 'application/json',
                #    'User-Agent': f'RiotClient/{self.useragent} %s (Windows;10;;Professional, x64)',
                # })

                # r=session.get('https://email-verification.riotgames.com/api/v1/account/status',headers=headers,json={},proxies=sys.getproxy(self.proxlist)).text

                # mailverif=r.split(',"emailVerified":')[1].split('}')[0]

                mailverif = bool(data['email_verified'])

            except Exception:
                # input(Exception)
                mailverif = True
            mailverif = bool(not mailverif)
            account.tokenid = str(token_id)
            account.token = str(token)
            account.entt = str(entitlement)
            account.puuid = str(puuid)
            account.unverifiedmail = str(mailverif)
            account.banuntil = banuntil
            account.gamename = str(gamename)
            account.tagline = str(tagline)
            account.registerdate = registerdatepatched
            if self.isDebug:
                print(puuid)
                print(entitlement+"\n-------")
                print(token+"\n-------")
                print(token_id)
                input()
            return account
        except Exception as e:
            input(traceback.format_exc())
            account.errmsg = str(traceback.format_exc())
            account.code = int(2)
            return account

import time
import pyupbit
import datetime
import schedule
from fbprophet import Prophet
import requests
import traceback
import logging
import numpy as np


logging.basicConfig(filename='./error_log_KNC.log',level=logging.ERROR)

access = ""
secret = ""
myToken = ""

Coin_list = ['KRW-ETH','KRW-KNC','KRW-BORA']

def post_message(token, channel, text):
    """슬랙 메시지 전송"""
    response = requests.post("https://slack.com/api/chat.postMessage",
        headers={"Authorization": "Bearer "+token},
        data={"channel": channel,"text": text}
    )
    if response.ok:
        print(text)
    else:
        print('send fail')

def get_target_price(ticker, k):
    """변동성 돌파 전략으로 매수 목표가 조회"""
    df = pyupbit.get_ohlcv(ticker, interval="day", count=2)
    target_price = df.iloc[0]['close'] + (df.iloc[0]['high'] - df.iloc[0]['low']) * k
    return target_price

def get_start_time(ticker):
    """시작 시간 조회"""
    df = pyupbit.get_ohlcv(ticker, interval="day", count=1)
    start_time = df.index[0]
    return start_time

def get_balance(ticker):
    """잔고 조회"""
    balances = upbit.get_balances()
    for b in balances:
        if b['currency'] == ticker:
            if b['balance'] is not None:
                return float(b['balance'])
            else:
                return 0
    return 0

def get_current_price(ticker):
    """현재가 조회"""
    return pyupbit.get_orderbook(ticker=ticker)["orderbook_units"][0]["ask_price"]


def get_ror(k=0.5):
    """ror 구하기"""
    df = pyupbit.get_ohlcv("KRW-KNC", count=7)
    df['range'] = (df['high'] - df['low']) * k
    df['target'] = df['open'] + df['range'].shift(1)

    df['ror'] = np.where(df['high'] > df['target'],
                         df['close'] / df['target'],
                         1)

    ror = df['ror'].cumprod()[-2]
    return ror


def get_new_k():
    """새로운 k값 구하기"""
    a = {}
    for k in np.arange(0.1, 1.0, 0.1):
        ror = get_ror(k)
        a['%.1f'% k] = '%f'% ror
    max_key = max(a,key=a.get)
    return max_key

predicted_close_price = 0
def predict_price(ticker):
    """Prophet으로 당일 종가 가격 예측"""
    global predicted_close_price
    df = pyupbit.get_ohlcv(ticker, interval="minute60")
    df = df.reset_index()
    df['ds'] = df['index']
    df['y'] = df['close']
    data = df[['ds','y']]
    model = Prophet()
    model.fit(data)
    future = model.make_future_dataframe(periods=24, freq='H')
    forecast = model.predict(future)
    closeDf = forecast[forecast['ds'] == forecast.iloc[-1]['ds'].replace(hour=9)]
    if len(closeDf) == 0:
        closeDf = forecast[forecast['ds'] == data.iloc[-1]['ds'].replace(hour=9)]
    closeValue = closeDf['yhat'].values[0]
    predicted_close_price = closeValue

predict_price("KRW-KNC")
schedule.every().hour.do(lambda: predict_price("KRW-KNC"))

# 로그인
upbit = pyupbit.Upbit(access, secret)
print("autotrade start")
# 시작 메세지 슬랙 전송
post_message(myToken,"#upbit_auto", "auto trade has been started_KNC")

# 자동매매 시작
krw_total = get_balance("KRW")
fixed_k = float(get_new_k())
post_message(myToken,"#upbit_auto", fixed_k)
print(fixed_k)
while True:
    try:
        now = datetime.datetime.now()
        start_time = get_start_time("KRW-BTC")
        # end_time = start_time + datetime.timedelta(minutes=30)
        end_time = start_time + datetime.timedelta(days=1)
        schedule.run_pending()

        #매수
        if start_time < now < end_time - datetime.timedelta(seconds=10):
            target_price = get_target_price("KRW-KNC", fixed_k)
            print('target_price')
            print(target_price)
            current_price = get_current_price("KRW-KNC")
            print('current_price')
            print(current_price)
            print('predicted_close_price')
            print(predicted_close_price)
            if target_price < current_price and current_price < predicted_close_price:
                krw = get_balance("KRW")  #현재 잔고
                if krw >= krw_total * 2/3:
                    if krw > 5000 : #최소 거래 금액
                        upbit.buy_market_order("KRW-KNC", krw*1/3)
                        post_message(myToken,"#upbit_auto", "KRW-KNC" + " bought ")

        #매도
        else:
            coin_balance = get_balance("KNC")
            current_price = get_current_price("KRW-KNC")
            fixed_k = float (get_new_k())
            print('coin_balance')
            print(coin_balance)
            print('current_price')
            print(current_price)
            print('new_k')
            print(fixed_k)
            post_message(myToken,"#upbit_auto", 'KNC')
            post_message(myToken,"#upbit_auto", fixed_k)

            if coin_balance > 5100 / current_price: #최소 거래금액 5,000원 이므로
                upbit.sell_market_order("KRW-KNC", coin_balance*0.9995)
                post_message(myToken,"#upbit_auto", "KRW-KNC " + " sold " )
                krw_total = get_balance("KRW")

        time.sleep(1)


    except Exception as e:
        logging.error(traceback.format_exc())
        post_message(myToken,'#upbit_auto', 'KNC Error')
        post_message(myToken,'#upbit_auto', e)
        time.sleep(1)
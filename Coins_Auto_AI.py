import time
import pyupbit
import datetime
import schedule
from fbprophet import Prophet
import requests
import re

access = ""
secret = ""
myToken = ""

Coin_list = ['KRW-ETH','KRW-KNC','KRW-BORA']
Coin_num = len(Coin_list)

def post_message(token, channel, text):
    """슬랙 메시지 전송"""
    response = requests.post("https://slack.com/api/chat.postMessage",
        headers={"Authorization": "Bearer "+token},
        data={"channel": channel,"text": text}
    )
    if response.ok:
        print('send success')
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
        else:
            return 0

def get_current_price(ticker):
    """현재가 조회"""
    return pyupbit.get_orderbook(ticker=ticker)["orderbook_units"][0]["ask_price"]

predicted_close_price = {}
for dic_coin in Coin_list:
    predicted_close_price[dic_coin] = 0
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
    predicted_close_price[ticker] = closeValue
    print(predicted_close_price)
for schedule_coins in Coin_list:
    predict_price(schedule_coins)
for schedule_coins in Coin_list:
    schedule.every().hour.do(lambda: predict_price(schedule_coins))

# 로그인
upbit = pyupbit.Upbit(access, secret)
print("autotrade start")
# 시작 메세지 슬랙 전송
post_message(myToken,"#bit_auto_", "auto trade has been started")

# 자동매매 시작
while True:
    try:
        now = datetime.datetime.now()
        start_time = get_start_time("KRW-BTC") + datetime.timedelta(minutes=5)
        end_time = start_time + datetime.timedelta(hours=23, minutes=30)
        # end_time = start_time + datetime.timedelta(minutes=6)
        schedule.run_pending()

        for coin in Coin_list:
            #매수
            if start_time < now < end_time - datetime.timedelta(seconds=10):
                target_price = get_target_price(coin, 0.5)
                print(coin)
                print(target_price)
                current_price = get_current_price(coin)
                print(current_price)
                print(predicted_close_price[coin])
                if target_price < current_price and current_price < predicted_close_price[coin]:
                    print("구매 시작")
                    krw = get_balance("KRW") / Coin_num  #현재 잔고
                    print(krw)
                    if krw > 5000: #최소 거래 금액
                        buy_result = upbit.buy_market_order(coin, krw*0.9995)
                        print(buy_result)
                        post_message(myToken,"#bit_auto_", str(coin) + " buy : " +str(buy_result) + '/ Balance : '+ str(krw))
            #매도
            else:
                coin_bal = re.sub('KRW-','',coin) 
                coin_balance = get_balance(coin_bal)
                current_price = get_current_price(coin)
                print(coin_balance)
                print(current_price)

                if coin_balance > 5500 / current_price: #최소 거래금액 5,000원 이므로
                    print('여기2')
                    sell_result = upbit.sell_market_order(coin, coin_balance*0.9995)
                    print(sell_result)
                    post_message(myToken,"#bit_auto_", str(coin) + " sell : " +str(sell_result) + '/ Balance : ' + str(krw))
                    print(sell_result)
            time.sleep(1)


    except Exception as e:
        print(e)
        post_message(myToken,'#bit_auto_', e)
        time.sleep(1)
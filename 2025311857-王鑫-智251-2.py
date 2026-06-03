# coding=utf-8
from gm.api import *
import pandas as pd

# ---------------------------- 策略配置参数 ----------------------------
strategy_id = 'test'
token = '955b0bb8eedbe9f89cfdf4fecb93f49b29a330fa'

SYMBOL = 'SZSE.002138'   # 顺络电子
SHORT_WINDOW = 5
LONG_WINDOW = 20
STOP_LOSS_RATIO = 0.05   # 5%止损
TAKE_PROFIT_RATIO = 0.15 # 15%止盈
# --------------------------------------------------------------------
def init(context):
    context.symbol = SYMBOL
    context.short_window = SHORT_WINDOW
    context.long_window = LONG_WINDOW
    context.stop_loss_ratio = STOP_LOSS_RATIO
    context.take_profit_ratio = TAKE_PROFIT_RATIO
    context.entry_price = 0.0 # 持仓成本价

    # 订阅日线数据
    subscribe(symbols=context.symbol,frequency='1d')
    print(f'策略初始化完成，交易标的：{context.symbol}')

def on_bar(context, bars):
    bar = bars[0]
    if bar['symbol'] != context.symbol:
        return
    current_price = bar['close']
    df = history_n(symbol=context.symbol, frequency='1d', count=context.long_window + 20, fields='close', end_time=bar['bob'])
    df = pd.DataFrame(df)
    close_prices = df['close']
    if len(close_prices) < context.long_window:
        return

    # 计算均线
    close_prices['ma5'] = close_prices.rolling(context.short_window).mean()
    close_prices['ma20'] = close_prices.rolling(context.long_window).mean()
    # 剔除均线未成型的空行
    df_ma = close_prices.dropna()
    if len(df_ma) < 2:
        return

    # 取最新两根均线用于交叉判断
    pre_short, pre_long = df_ma.iloc[-2]['ma5'], df_ma.iloc[-2]['ma20']
    now_short, now_long = df_ma.iloc[-1]['ma5'], df_ma.iloc[-1]['ma20']

    golden_cross = pre_short <= pre_long and now_short > now_long  # 金叉买入
    dead_cross = pre_short >= pre_long and now_short < now_long   # 死叉卖出
    account = context.account()
    pos = account.position(symbol=context.symbol, side=PositionSide_Long)
    pos_vol = pos['volume'] if pos else 0
    if pos_vol > 0:
        context.entry_price = pos['vwap']
    else:
        context.entry_price = 0

    cash = account.cash['available']

    # 止盈止损判定
    sl_trig, tp_trig = False, False
    if pos_vol > 0 and context.entry_price > 0:
        profit_rate = (current_price - context.entry_price) / context.entry_price
        if profit_rate <= -context.stop_loss_ratio:
            sl_trig = True
        if profit_rate >= context.take_profit_ratio:
            tp_trig = True

    # 交易逻辑
    # 金叉 + 无持仓 → 满仓买入
    if golden_cross and pos_vol == 0:
        lot = 100
        buy_num = int((cash // current_price) // lot) * lot
        if buy_num >= lot:
            order_volume(symbol=context.symbol, volume=buy_num, side=OrderSide_Buy,
                         order_type=OrderType_Market, position_effect=PositionEffect_Open)
            print(f"金叉开仓：买入{buy_num}股，价格{current_price:.2f}")

    # 死叉 / 止损 / 止盈 任一触发+有持仓 → 全平
    elif (dead_cross or sl_trig or tp_trig) and pos_vol > 0:
        order_volume(symbol=context.symbol, volume=pos_vol, side=OrderSide_Sell,
                     order_type=OrderType_Market, position_effect=PositionEffect_Close)
        print(f"平仓卖出{pos_vol}股，价{current_price:.2f},死叉{dead_cross},止损{sl_trig},止盈{tp_trig}")

def on_order_status(context, order):
    print(f'订单{order.order_id} 状态：{order.status}')

def on_backtest_finished(context, indicator):
    print("\n========回测结果汇总========")
    print(f"总收益率：{indicator['pnl_ratio']*100:.2f}%")
    print(f"最大回撤：{indicator['max_drawdown']*100:.2f}%")
    print(f"夏普比率：{indicator['sharp_ratio']:.3f}")
    print(f"期末总资产：{indicator['total_value']:.2f}")

if __name__ == '__main__':
    run(strategy_id=strategy_id,
        token=token,
        filename='main.py',
        mode=MODE_BACKTEST,
        backtest_start_time='2022-01-01 09:00:00',
        backtest_end_time='2023-12-31 15:00:00',
        backtest_initial_cash=100000, # 初始资金10万（和案例统一）
        backtest_adjust=ADJUST_PREV, # 前复权
        backtest_commission_ratio=0.0002,
        backtest_slippage_ratio=0.001)
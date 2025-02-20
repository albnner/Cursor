# -*- coding: utf-8 -*-
import numpy as np
from datetime import datetime, timedelta
import logging

def init(context):
    # 初始化日志
    log.set_level('debug')
    
    # 基本参数
    context.account_id = '620000095252'
    context.stock_pool = ['SHSE.600519', 'SZSE.000858', 'SHSE.600036']
    context.set_universe(context.stock_pool)
    context.max_cup_days = 90       # 最大杯部检测周期
    context.max_handle_days = 30    # 最大柄部检测周期
    context.adjust_mode = 'back'    # 后复权

    context.start_date = '20200101'  # 回测开始日期
    context.end_date = '20231231'    # 回测结束日期
    
    # 形态参数
    context.cup_retrace_min = 0.25  # 杯部最小回撤
    context.handle_retrace_max = 0.03  # 柄部最大回撤
    context.volume_ratio = 0.65     # 柄部成交量比例
    
    # 波动率参数
    context.atr_period = 14
    context.cup_vol_max = 0.08      # 杯部年化波动率上限
    context.handle_vol_max = 0.05   # 柄部年化波动率上限

    # 趋势参数
    context.cup_slope_min = 0.2   # 杯右最小斜率
    context.handle_slope_max = 0.4  # 柄部最大斜率绝对值

    context.stop_loss = 0.08  # 固定止损比例8%
    context.take_profit = 0.20  # 固定止盈比例20%
    context.trailing_stop = 0.10  # 回落止盈回撤比例10%
    context.trailing_mode = True  # 是否启用回落止盈

def handlebar(context):
    now_time = timetag_to_datetime(context.get_bar_timetag(context.barpos),"%Y%m%d")
    len=context.max_cup_days + context.max_handle_days,
    start_time = (datetime.strptime(now_time,"%Y%m%d")-timedelta(days = len)).strftime("%Y%m%d")

    # 在原有逻辑前添加止损检查
    check_stop_conditions(context)

    try:
        for security in context.stock_pool:
            # if not check_trading_status(security):
            #     continue
            
            # 获取历史数据
            price_df = context.get_market_data(
                        stock_code=security,
                        start_date=start_time,
                        end_date=now_time,
                        period='1d',
                        field=['open','high','low','close','volume'],
                        dividend_type=context.adjust_mode,
                    )
            if price_df is None:
                continue
            
            # 动态周期检测
            signal = detect_cup_handle(context, price_df)
            
            if signal:

                # log.info(f"发现买点 {security} 周期:{signal['days']} 价格:{price_df['close'].iloc[0]}")
                print(f"发现买点 {security} 周期:{signal['days']} 价格:{price_df['close'].iloc[0]}")
                place_order(context, security)
                
    except Exception as e:
        # log.error(f"主循环异常: {str(e)}")
        print(f"主循环异常: {str(e)}")

def detect_cup_handle(context, price_df):
    """动态检测杯柄形态"""
    try:
        for cup_days in range(40, 81, 5):
            for handle_days in range(10, 26, 3):
                if len(price_df) < cup_days + handle_days:
                    continue
                
                cup = price_df[-(cup_days+handle_days):-handle_days]
                handle = price_df[-handle_days:]
                
                if (check_cup_condition(context, cup) and 
                    check_handle_condition(context, cup, handle) and
                    check_volatility(context, cup, handle) and
                    check_trend(context, cup, handle)):
                    return {'days': f"{cup_days}/{handle_days}"}
        return None
    except Exception as e:
        # log.error(f"形态检测异常: {str(e)}")
        print(f"形态检测异常: {str(e)}")
        return None

def check_cup_condition(context, cup):
    """杯部条件验证"""
    try:
        min_idx = cup['low'].values.argmin()
        return (
            (min_idx <= len(cup)//3) and # 底部在前1/3区间
            (cup['close'].iloc[-1] > cup['close'].iloc[0] * 1.15) and  # 15%涨幅
            (calculate_retracement(cup) >= context.cup_retrace_min) # 回撤≥25%
        )
    except IndexError as e:
        # log.warning(f"杯部数据索引异常: {str(e)}")
        print(f"杯部数据索引异常: {str(e)}")
        return False

def check_handle_condition(context, cup, handle):
    """柄部条件验证"""
    try:
        return (
            (handle['high'].max() < cup['high'].max() * 0.97) and # 柄部高点低于前高3%
            (handle['low'].min() > cup['low'].min() * 1.05) and    # 柄部低点高于前低5%
            (handle['volume'].mean() < cup['volume'].mean() * context.volume_ratio) # 柄部成交量均值低于杯部65%
        )
    except KeyError as e:
        # log.warning(f"字段不存在: {str(e)}")
        print(f"字段不存在: {str(e)}")
        return False

def check_volatility(context, cup, handle):
    """波动率验证"""
    try:
        # 计算ATR
        cup_atr = calculate_atr(cup, context.atr_period)
        handle_atr = calculate_atr(handle, context.atr_period)
        
        # 计算年化波动率
        # cup_vol = cup['close'].pct_change().std() * np.sqrt(252)
        # handle_vol = handle['close'].pct_change().std() * np.sqrt(252)
        
        return (
            # (cup_vol < context.cup_vol_max) and
            # (handle_vol < context.handle_vol_max) and
            (handle_atr.mean() < cup_atr.mean() * 0.6)
        )
    except Exception as e:
        # log.error(f"波动率计算异常: {str(e)}")
        print(f"波动率计算异常: {str(e)}")
        return False

def check_trend(context, cup, handle):
    """趋势验证"""
    try:
        # 杯右趋势
        cup_slope = np.polyfit(range(10), cup['close'].iloc[-10:], 1)[0]
        # 柄部趋势
        handle_slope = np.polyfit(range(len(handle)), handle['close'], 1)[0]
        # 杯右的斜率为正（上升趋势），柄部的斜率绝对值小于0.5（波动平缓）
        return (cup_slope > context.cup_slope_min) and (abs(handle_slope) < context.handle_slope_max)
    except np.linalg.LinAlgError:
        # log.warning("趋势计算矩阵异常")
        print("趋势计算矩阵异常")
        return False

def place_order(context, security):
    """下单操作"""
    try:
        # if context.portfolio.positions[security].quantity == 0:
        context.entry_price = bar.close
        context.highest_price = bar.close  # 初始化最高价

        order_target_percent(
            security, 
            1, 
            'MARKET',
            context,
            context.account_id
        )
        # log.info(f"下单成功 {security}")
        print(f"下单成功 {security}")
    except TradingError as te:
        # log.error(f"交易失败 {security}: {te.order_id}")
        print(f"交易失败 {security}: {te.order_id}")
    except Exception as e:
        # log.error(f"下单异常 {security}: {str(e)}")
        print(f"下单异常 {security}: {str(e)}")

# ------------ 工具函数 ------------
def calculate_retracement(data):
    peak = data['high'].max()
    trough = data['low'].min()
    return (peak - trough) / peak

def calculate_atr(data, period):
    high, low, close = data['high'], data['low'], data['close']
    tr = np.maximum(high - low, 
                   np.maximum(abs(high - close.shift(1)), 
                             abs(low - close.shift(1))))
    return tr.rolling(period).mean()

'''
def check_trading_status(security):
    """检查交易状态"""
    instr = get_instrument(security)
    return not (instr.is_st or instr.status == '停牌')
'''

def check_stop_conditions(context):
    """止盈止损检查"""
    # 获取所有持仓
    try:
        holdings = get_trade_detail_data(context.accountid,'STOCK','POSITION')
    except Exception as e:
        print(f"获取持仓失败: {str(e)}")
        # log.error(f"获取持仓失败: {str(e)}")
        return

    for holding in holdings:

        security = holding.security
        
        # 获取持仓详情
        # hold_amount = holding.m_nVolume     # 持仓数量
        avg_cost = holding.m_dOpenPrice     # 平均成本
        profit = holding.m_dFloatProfit     # 浮动盈亏
        balance = holdings.m_nCanUseVolume  # 可用余额
        current_price = holdings.dSettlementPrice # 当前股价
        
        # 固定比例止损（8%）
        if balance > 0 and profit <= avg_cost * (1 - context.stop_loss):
            close_position(context, security, balance, "固定比例止损")
            continue
            
        # 固定比例止盈（20%）
        if balance > 0 and current_price >= avg_cost * (1 + context.take_profit):
            close_position(context, security, balance, "固定比例止盈")
            continue
            
        # 回落止盈（需要自行维护最高价）
        if context.trailing_mode:
            if not hasattr(context, 'price_highs'):
                context.price_highs = {}
            context.price_highs[security] = max(
                context.price_highs.get(security, current_price),
                current_price
            )
            high_price = context.price_highs[security]
            
            if current_price <= high_price * (1 - context.trailing_stop):
                close_position(context, security, balance, "回落止盈")
                    

def close_position(context, security, hold_am, reason):
    """平仓操作（iquant版）"""
    try:
        order_target(security, -1, 'MARKET', context, context.account_id)
        print(f"{reason}触发 {security} 价格:{price:.2f}")
        # log.info(f"{reason}触发 {security} 价格:{price:.2f}")
        # 清除最高价记录
        if hasattr(context, 'price_highs') and security in context.price_highs:
            del context.price_highs[security]
    except Exception as e:
        print(f"平仓失败 {security}: {str(e)}")
        # log.error(f"平仓失败 {security}: {str(e)}")

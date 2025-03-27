import numpy as np
from datetime import datetime, timedelta
import logging

def init(context):
    context.account_id = '620000095252'
    # 设置股票池（示例为沪深300成分股，可替换为其他股票池）
    context.stock_pool = context.get_sector('000300.SH', realtime)
    context.set_universe(context.stock_pool)

    context.max_days = 3 * 365         # 最大数据获取周期，3年
    
    context.screening_frequency = 1  # 设置筛选频率（按日筛选）

def handlebar(context):
    # 获取当前交易日
    current_date = timetag_to_datetime(context.get_bar_timetag(context.barpos),"%Y%m%d")
    start_date = (datetime.strptime(current_date,"%Y%m%d")-timedelta(days = context.max_days)).strftime("%Y%m%d")

    # 预筛选结果列表
    selected_stocks = []
    
    for stock in context.stock_pool:
        try:
            # 条件1: 实控人性质为国资（根据平台实际字段调整）
            # controller_type = get_factor(stock, 'actual_controller_type', current_date)
            # if controller_type != 'state-owned':
            #     continue
                
            # 条件2: 流通市值小于150亿
            circ_cap = get_financial_data([CAPITALSTRUCTURE.circulating_capital]，stock, 'circ_mv', start_date, current_date)  # 单位：亿元
            if circ_cap >= 150:
                continue
                
            # === 条件3: 估值条件 ===
            # 获取3年历史数据
            hist_data = context.get_market_data(
                stock_code=stock,
                start_date=(datetime.strptime(current_date, "%Y%m%d") - timedelta(days=3*365)).strftime("%Y%m%d"),
                end_date=current_date,
                field='close',
                dividend_type='back'
            )
            if len(hist_data) < 100:  # 至少100个交易日数据
                continue
                
            # 价格条件：当前价格位于后20%分位
            price_cond = price <= np.percentile(hist_data.close.values, 20)
            
            # PE条件：TTM市盈率
            pe_data = context.get_financials(
                stock_code=stock,
                report_type='valuation',
                fields='pe_ratio_ttm',
                period='latest'
            )
            pe_cond = 10 <= pe_data.iloc[0].value <= 18 if not pe_data.empty else False
            
            if not (price_cond or pe_cond):
                continue

            # === 条件4: 净利润稳定性 ===
            net_profit = context.get_financials(
                stock_code=stock,
                report_type='income',
                fields='net_profit',
                period='year',
                count=3
            )
            if len(net_profit) < 3:
                continue
                
            growth = [(net_profit.iloc[i].value - net_profit.iloc[i-1].value)/abs(net_profit.iloc[i-1].value) 
                     for i in range(1,3)]
            avg_growth = np.mean(growth)
            if avg_growth < 0.3 or np.std(growth) > 0.5:
                continue
                
            selected_stocks.append(stock)
            
        except Exception as e:
            log.warn(f"处理股票{stock}时发生错误: {str(e)}")
    
    # 输出最终筛选结果
    log.info(f"满足条件的股票列表：{selected_stocks}")
    return selected_stocks
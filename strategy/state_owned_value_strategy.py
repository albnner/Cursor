def initialize(context):
    # 设置股票池（示例为沪深300成分股，可替换为其他股票池）
    context.stock_pool = get_index_stocks('SH000300')
    # 设置筛选频率（按日筛选）
    context.screening_frequency = 1

def handle_data(context, data):
    # 获取当前交易日
    current_date = context.current_dt
    
    # 预筛选结果列表
    selected_stocks = []
    
    for stock in context.stock_pool:
        try:
            # 条件1: 实控人性质为国资（根据平台实际字段调整）
            controller_type = get_factor(stock, 'actual_controller_type', current_date)
            if controller_type != 'state-owned':
                continue
                
            # 条件2: 流通市值筛选
            circ_mv = get_factor(stock, 'circ_mv', current_date)  # 单位：亿元
            if circ_mv >= 150:
                continue
                
            # 条件3: 估值条件（价格或PE满足其一）
            # 3年价格低位（取最近250*3个交易日）
            hist_close = get_price(stock, '1d', '20000101', current_date, 'close')[-750:]
            current_price = data.current(stock, 'price')
            pe = get_factor(stock, 'pe_ratio', current_date)
            
            price_condition = (current_price <= hist_close.min() * 1.1)  # 价格在最低10%范围内
            pe_condition = (10 <= pe <= 18) if pe is not None else False
            if not (price_condition or pe_condition):
                continue
                
            # 条件4: 净利润稳定性（取最近3年年报数据）
            # ... existing code ...
            net_profit = get_financials(stock, 'net_profit', 'year', 3)  # 获取最近3年净利润
            if len(net_profit) < 3:
                continue
                
            # 计算增长率和波动性
            growth_rates = [(net_profit[i] - net_profit[i-1])/abs(net_profit[i-1]) 
                          for i in range(1, len(net_profit))]
            avg_growth = np.mean(growth_rates)
            growth_std = np.std(growth_rates)
            
            # 要求：最近两年平均增长率>30%且波动率<50%
            if avg_growth < 0.3 or growth_std > 0.5:
                continue
                
            selected_stocks.append(stock)
            
        except Exception as e:
            log.warn(f"处理股票{stock}时发生错误: {str(e)}")
    
    # 输出最终筛选结果
    log.info(f"满足条件的股票列表：{selected_stocks}")
    return selected_stocks
def initialize(context):
    # 更新后的证券代码格式要求
    context.stock_pool = ['SHSE.600519', 'SZSE.000858', 'SHSE.600036']  
    # 时间参数改用datetime格式
    context.start_time = '2020-01-01'
    context.end_time = '2023-12-31'
    
    # 新增复权参数设置
    context.adjust_mode = 'post'  # 后复权
    context.cup_duration = 60
    context.handle_duration = 15
    context.volume_ratio = 0.65  # 柄部成交量萎缩比例阈值

def handle_data(context, data):
    current_date = get_datetime().strftime('%Y-%m-%d')  # 改用标准时间获取函数
    
    for security in context.stock_pool:
        # 更新后的数据接口（文档第17页示例）
        try:
            price_df = get_price(security,
                           start_date=context.start_time,
                           end_date=current_date,
                           frequency='daily',
                           fields=['open','high','low','close','volume'],
                           adjust_mode=context.adjust_mode,
                           skip_suspended=True,
                           fq_ref_date=current_date)
        # 异常处理
        except DataRequestError as e:
            log_error(f"数据获取失败：{str(e)}")
        except TradingError as te:
            log_error(f"交易指令失败：{te.order_id}")
        
        
        if len(price_df) < context.cup_duration + context.handle_duration:
            continue
            
        # 切片方式更新（最新API返回时间升序）
        cup_data = price_df[-context.cup_duration-context.handle_duration:-context.handle_duration]
        handle_data = price_df[-context.handle_duration:]
        
        # 增强的杯型条件判断
        cup_condition = (
            # 将精确匹配改为范围判断
            (cup_data['low'].values.argmin() <= context.cup_duration // 3) and  # 位置在前1/3区间
            (cup_data['close'].iloc[-1] > cup_data['close'].iloc[0] * 1.2) and
            (calculate_retracement(cup_data) >= 0.3)
        )
        
        # 柄部条件强化
        handle_condition = (
            (handle_data['high'].max() < cup_data['high'].max() * 0.98) and
            (handle_data['low'].min() > cup_data['low'].min() * 1.1) and
            (handle_data['volume'].mean() < cup_data['volume'].mean() * context.volume_ratio)
        )
        
        if cup_condition and handle_condition:
            # 更新后的交易接口（需绑定真实账户）
            order_target_percent(security, 0.1, 
                               price=handle_data['close'].iloc[-1],
                               order_type=OrderType.Limit,
                               account='您的账户ID')  # 需替换真实账户

def check_additional_conditions(df):
    # 验证30日均线上扬
    ma30 = df['close'].rolling(30).mean()
    if ma30[-10:].pct_change().mean() <= 0:
        return False
        
    # 验证MACD底背离
    macd_line = calculate_macd(df['close'])
    if macd_line[-1] > macd_line[-5]:
        return False
        
    return True


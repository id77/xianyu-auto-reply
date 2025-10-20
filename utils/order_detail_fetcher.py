"""
闲鱼订单详情获取工具 - API版本
使用HTTP请求替代Playwright，更加可靠和高效
"""

import time
import json
from typing import Optional, Dict, Any
import requests
from loguru import logger
import re
import urllib3

from config import DEFAULT_HEADERS
from utils.xianyu_utils import generate_sign, trans_cookies

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class OrderDetailAPIFetcher:
    """闲鱼订单详情获取器 - API版本"""
    
    def __init__(self, cookie_string: str = None):
        self.session = requests.Session()
        self.cookie_string = cookie_string
        self.base_url = "https://h5api.m.goofish.com/h5"
        
        # 禁用SSL证书验证以解决证书问题
        self.session.verify = False
        
        headers = DEFAULT_HEADERS.copy()

        # 设置基础请求头
        self.headers = {
            "accept": "application/json",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "referer": "https://www.goofish.com/",
            "sec-ch-ua": '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": headers['user-agent'] or  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        }
        
        if self.cookie_string:
            self.headers["cookie"] = self.cookie_string
        
        self.session.headers.update(self.headers)
        
        # API相关配置
        self.app_key = "34839810"  # 从HAR文件中获得的appKey
        self.api_version = "1.0"
        
    def _generate_sign(self, api_name: str, data: str, t: str, app_key: str) -> str:
        """
        生成API签名 - 使用xianyu_utils中的generate_sign函数
        """
        try:
            # 从cookie中提取token
            token = ""
            if self.cookie_string:
                cookies = trans_cookies(self.cookie_string)
                m_h5_tk = cookies.get('_m_h5_tk', '')
                if m_h5_tk:
                    token = m_h5_tk.split('_')[0]
            
            # 使用xianyu_utils的generate_sign函数
            sign = generate_sign(t, token, data)
            return sign
        except Exception as e:
            logger.error(f"生成签名失败: {e}")
            return ""
    
    def _get_token_and_session(self) -> tuple:
        """
        从cookie中提取token和session信息
        """
        try:
            if not self.cookie_string:
                return "", ""
                
            # 提取 _m_h5_tk
            token_match = re.search(r'_m_h5_tk=([^;]+)', self.cookie_string)
            token = token_match.group(1) if token_match else ""
            
            # 提取 JSESSIONID 或其他session标识
            session_match = re.search(r'JSESSIONID=([^;]+)', self.cookie_string)
            session = session_match.group(1) if session_match else ""
            
            return token, session
        except Exception as e:
            logger.error(f"提取token和session失败: {e}")
            return "", ""
    
    def _build_request_data(self, order_id: str) -> Dict[str, Any]:
        """
        构建请求数据 - 基于HAR文件中的真实请求
        """
        return {
            "tid": order_id  # HAR文件中使用的是tid，不是orderId
        }
    
    async def fetch_order_detail(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        获取订单详情
        
        Args:
            order_id: 订单ID
            
        Returns:
            包含订单详情的字典，失败时返回None
        """
        try:
            logger.info(f"开始获取订单详情: {order_id}")
            
            # 检查数据库缓存
            try:
                from db_manager import db_manager
                existing_order = db_manager.get_order_by_id(order_id)
                
                if existing_order:
                    # 检查金额字段是否有效
                    amount = existing_order.get('amount', '')
                    amount_valid = False
                    
                    if amount:
                        amount_clean = str(amount).replace('¥', '').replace('￥', '').replace('$', '').strip()
                        try:
                            amount_value = float(amount_clean)
                            amount_valid = amount_value > 0
                        except (ValueError, TypeError):
                            amount_valid = False
                    
                    if amount_valid:
                        logger.info(f"📋 订单 {order_id} 已存在于数据库中且金额有效({amount})，直接返回缓存数据")
                        
                        result = {
                            'order_id': existing_order['order_id'],
                            'url': f"https://www.goofish.com/order-detail?orderId={order_id}&role=seller",
                            'title': f"订单详情 - {order_id}",
                            'sku_info': {
                                'spec_name': existing_order.get('spec_name', ''),
                                'spec_value': existing_order.get('spec_value', ''),
                                'quantity': existing_order.get('quantity', ''),
                                'amount': existing_order.get('amount', '')
                            },
                            'spec_name': existing_order.get('spec_name', ''),
                            'spec_value': existing_order.get('spec_value', ''),
                            'quantity': existing_order.get('quantity', ''),
                            'amount': existing_order.get('amount', ''),
                            'buyer_nickName': existing_order.get('buyer_nickName', ''),
                            'buyer_name': existing_order.get('buyer_name', ''),
                            'buyer_phone': existing_order.get('buyer_phone', ''),
                            'buyer_address': existing_order.get('buyer_address', ''),
                            'timestamp': time.time(),
                            'from_cache': True
                        }
                        return result
            except Exception as e:
                logger.warning(f"检查数据库缓存失败: {e}")
            
            # 准备API请求
            api_name = "mtop.idle.web.trade.order.detail"
            timestamp = str(int(time.time() * 1000))
            
            # 构建请求数据
            request_data = self._build_request_data(order_id)
            data_json = json.dumps(request_data, separators=(',', ':'))
            
            # 获取token信息
            token, session = self._get_token_and_session()
            
            # 生成签名
            sign = self._generate_sign(api_name, data_json, timestamp, self.app_key)
            
            # 构建请求URL和参数
            params = {
                "jsv": "2.7.2",
                "appKey": self.app_key,
                "t": timestamp,
                "sign": sign,
                "v": self.api_version,
                "type": "originaljson",
                "accountSite": "xianyu",
                "dataType": "json",
                "timeout": "20000",
                "api": api_name,
                "sessionOption": "AutoLoginOnly"
            }
            
            # 构建POST数据
            post_data = {
                "data": data_json
            }
            
            # 发送请求
            url = f"{self.base_url}/{api_name}/{self.api_version}/"
            
            logger.info(f"请求URL: {url}")
            logger.info(f"请求参数: {params}")
            logger.info(f"POST数据: {post_data}")
            
            response = self.session.post(url, params=params, data=post_data, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"API请求失败，状态码: {response.status_code}")
                logger.error(f"响应内容: {response.text[:200]}")
                return None
            
            # 解析响应
            response_text = response.text
            logger.info(f"API响应: {response_text[:500]}...")  # 只打印前500字符
            
            # 处理JSON响应（不是JSONP）
            try:
                response_data = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败: {e}")
                logger.error(f"响应内容: {response_text[:200]}")
                return None
            
            # 检查响应状态
            ret_list = response_data.get('ret', [])
            if not ret_list or not ret_list[0].startswith('SUCCESS'):
                logger.error(f"API调用失败: {ret_list}")
                return None
            
            # 解析订单数据
            order_data = response_data.get('data', {})
            return self._parse_order_data(order_data, order_id)
            
        except Exception as e:
            logger.error(f"获取订单详情失败: {e}")
            return None
    
    def _parse_order_data(self, order_data: Dict[str, Any], order_id: str) -> Dict[str, Any]:
        """
        解析订单数据 - 基于HAR文件中的真实响应结构
        """
        try:
            # 从HAR响应可以看出真实的数据结构
            logger.info(f"开始解析订单数据，订单ID: {order_id}")
            logger.debug(f"原始订单数据结构: {order_data.keys() if order_data else 'None'}")
            
            # 提取地址信息 - 从components中的addressInfoVO
            buyer_name = ""
            buyer_phone = ""
            buyer_address = ""
            
            components = order_data.get('components', [])
            
            # 提取商品和价格信息 - 从components中的orderInfoVO
            spec_name = ""
            spec_value = ""
            quantity = "1"
            amount = ""
            title = ""
            skuInfo = ""
            buyer_nickName = ""
            
            for component in components:
                if component.get('render') == 'addressInfoVO':
                    address_data = component.get('data', {})
                    buyer_name = address_data.get('name', '')
                    buyer_phone = address_data.get('phoneNumber', '')
                    buyer_address = address_data.get('address', '')
                if component.get('render') == 'orderInfoVO':
                    order_info_data = component.get('data', {})
                    
                    # 提取商品信息
                    item_info = order_info_data.get('itemInfo', {})
                    title = item_info.get('title', '')
                    skuInfo = item_info.get('skuInfo', '')
                    quantity = str(item_info.get('buyAmount', 1))
                    item_price = item_info.get('price', '')
                    
                    # 提取价格信息
                    price_info = order_info_data.get('priceInfo', {})
                    amount_info = price_info.get('amount', {})
                    amount = amount_info.get('value', '') or item_price
                    
                    # 提取买家昵称
                    order_info_list = order_info_data.get('orderInfoList', [])
                    for info in order_info_list:
                        if info.get('title') == '买家昵称':
                            buyer_nickName = info.get('value', '')
                            break
                    
            
            
            # 商品标题作为规格名称
            spec_name = title
            spec_value = skuInfo
            
            result = {
                'order_id': order_id,
                'url': f"https://www.goofish.com/order-detail?orderId={order_id}&role=seller",
                'title': f"订单详情 - {order_id}",
                'sku_info': {
                    'spec_name': spec_name,
                    'spec_value': spec_value,
                    'quantity': quantity,
                    'amount': amount
                },
                'spec_name': spec_name,
                'spec_value': spec_value,
                'quantity': quantity,
                'amount': amount,
                'buyer_nickName': buyer_nickName,
                'buyer_name': buyer_name,
                'buyer_phone': buyer_phone,
                'buyer_address': buyer_address,
                'timestamp': time.time(),
                'from_cache': False
            }
            
            logger.info(f"订单详情解析成功: {order_id}")
            logger.debug(f"解析结果: 商品={spec_name}, 数量={quantity}, 金额={amount}, 买家={buyer_nickName}")
            return result
            
        except Exception as e:
            logger.error(f"解析订单数据失败: {e}")
            return None


# 便捷函数
async def fetch_order_detail_api(order_id: str, cookie_string: str = None, use_cache: bool = True) -> Optional[Dict[str, Any]]:
    """
    使用API方式获取订单详情的便捷函数
    
    Args:
        order_id: 订单ID
        cookie_string: Cookie字符串
        use_cache: 是否使用数据库缓存，默认True。设为False时强制从API获取
        
    Returns:
        订单详情字典，失败时返回None
    """
    # 检查数据库缓存（仅在use_cache为True时）
    if use_cache:
        try:
            from db_manager import db_manager
            existing_order = db_manager.get_order_by_id(order_id)
            
            if existing_order:
                # 检查金额字段是否有效
                amount = existing_order.get('amount', '')
                amount_valid = False
                
                if amount:
                    amount_clean = str(amount).replace('¥', '').replace('￥', '').replace('$', '').strip()
                    try:
                        amount_value = float(amount_clean)
                        amount_valid = amount_value > 0
                    except (ValueError, TypeError):
                        amount_valid = False
                
                if amount_valid:
                    logger.info(f"📋 订单 {order_id} 已存在于数据库中且金额有效({amount})，直接返回缓存数据")
                    
                    result = {
                        'order_id': existing_order['order_id'],
                        'url': f"https://www.goofish.com/order-detail?orderId={order_id}&role=seller",
                        'title': f"订单详情 - {order_id}",
                        'sku_info': {
                            'spec_name': existing_order.get('spec_name', ''),
                            'spec_value': existing_order.get('spec_value', ''),
                            'quantity': existing_order.get('quantity', ''),
                            'amount': existing_order.get('amount', '')
                        },
                        'spec_name': existing_order.get('spec_name', ''),
                        'spec_value': existing_order.get('spec_value', ''),
                        'quantity': existing_order.get('quantity', ''),
                        'amount': existing_order.get('amount', ''),
                        'buyer_nickName': existing_order.get('buyer_nickName', ''),
                        'buyer_name': existing_order.get('buyer_name', ''),
                        'buyer_phone': existing_order.get('buyer_phone', ''),
                        'buyer_address': existing_order.get('buyer_address', ''),
                        'timestamp': time.time(),
                        'from_cache': True
                    }
                    return result
        except Exception as e:
            logger.warning(f"检查数据库缓存失败: {e}")
    else:
        logger.info(f"跳过缓存检查，直接从API获取订单详情: {order_id}")
    
    # 创建fetcher并获取数据
    fetcher = OrderDetailAPIFetcher(cookie_string)
    return await fetcher.fetch_order_detail(order_id)


# 同步版本的便捷函数
def fetch_order_detail_api_sync(order_id: str, cookie_string: str = None, use_cache: bool = True) -> Optional[Dict[str, Any]]:
    """
    使用API方式获取订单详情的同步便捷函数
    
    Args:
        order_id: 订单ID
        cookie_string: Cookie字符串
        use_cache: 是否使用数据库缓存，默认True。设为False时强制从API获取
    
    Returns:
        订单详情字典，失败时返回None
    """
    try:
        # 检查数据库缓存（仅在use_cache为True时）
        if use_cache:
            try:
                from db_manager import db_manager
                existing_order = db_manager.get_order_by_id(order_id)
                
                if existing_order:
                    # 检查金额字段是否有效
                    amount = existing_order.get('amount', '')
                    amount_valid = False
                    
                    if amount:
                        amount_clean = str(amount).replace('¥', '').replace('￥', '').replace('$', '').strip()
                        try:
                            amount_value = float(amount_clean)
                            amount_valid = amount_value > 0
                        except (ValueError, TypeError):
                            amount_valid = False
                    
                    if amount_valid:
                        logger.info(f"📋 订单 {order_id} 已存在于数据库中且金额有效({amount})，直接返回缓存数据")
                        
                        result = {
                            'order_id': existing_order['order_id'],
                            'url': f"https://www.goofish.com/order-detail?orderId={order_id}&role=seller",
                            'title': f"订单详情 - {order_id}",
                            'sku_info': {
                                'spec_name': existing_order.get('spec_name', ''),
                                'spec_value': existing_order.get('spec_value', ''),
                                'quantity': existing_order.get('quantity', ''),
                                'amount': existing_order.get('amount', '')
                            },
                            'spec_name': existing_order.get('spec_name', ''),
                            'spec_value': existing_order.get('spec_value', ''),
                            'quantity': existing_order.get('quantity', ''),
                            'amount': existing_order.get('amount', ''),
                            'buyer_nickName': existing_order.get('buyer_nickName', ''),
                            'buyer_name': existing_order.get('buyer_name', ''),
                            'buyer_phone': existing_order.get('buyer_phone', ''),
                            'buyer_address': existing_order.get('buyer_address', ''),
                            'timestamp': time.time(),
                            'from_cache': True
                        }
                        return result
            except Exception as e:
                logger.warning(f"检查数据库缓存失败: {e}")
        else:
            logger.info(f"跳过缓存检查，直接从API获取订单详情: {order_id}")
        
        # 创建fetcher并获取数据
        fetcher = OrderDetailAPIFetcher(cookie_string)
        
        # 同步调用（去掉async/await）
        logger.info(f"开始API获取订单详情: {order_id}")
        
        # 准备API请求
        api_name = "mtop.idle.web.trade.order.detail"
        timestamp = str(int(time.time() * 1000))
        
        # 构建请求数据
        request_data = fetcher._build_request_data(order_id)
        data_json = json.dumps(request_data, separators=(',', ':'))
        
        # 获取token信息
        token, session = fetcher._get_token_and_session()
        
        # 生成签名
        sign = fetcher._generate_sign(api_name, data_json, timestamp, fetcher.app_key)
        
        # 构建请求URL和参数
        params = {
            "jsv": "2.7.2",
            "appKey": fetcher.app_key,
            "t": timestamp,
            "sign": sign,
            "v": fetcher.api_version,
            "type": "originaljson",
            "accountSite": "xianyu", 
            "dataType": "json",
            "timeout": "20000",
            "api": api_name,
            "sessionOption": "AutoLoginOnly",
            "spm_cntl": "a21ybx.order-detail.0.0"
        }
        
        # 构建POST数据
        post_data = {
            "data": data_json
        }
        
        # 发送请求
        url = f"{fetcher.base_url}/{api_name}/{fetcher.api_version}/"
        
        logger.info(f"请求URL: {url}")
        logger.info(f"请求参数: {params}")
        logger.info(f"POST数据: {post_data}")
        
        response = fetcher.session.post(url, params=params, data=post_data, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"API请求失败，状态码: {response.status_code}")
            logger.error(f"响应内容: {response.text[:200]}")
            return None
        
        # 解析响应
        response_text = response.text
        logger.info(f"API响应: {response_text[:500]}...")  # 只打印前500字符
        
        # 处理JSON响应（不是JSONP）
        try:
            response_data = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            logger.error(f"响应内容: {response_text[:200]}")
            return None
        
        # 检查响应状态
        ret_list = response_data.get('ret', [])
        if not ret_list or not ret_list[0].startswith('SUCCESS'):
            logger.error(f"API调用失败: {ret_list}")
            return None
        
        # 解析订单数据
        order_data = response_data.get('data', {})
        return fetcher._parse_order_data(order_data, order_id)
        
    except Exception as e:
        logger.error(f"API获取订单详情失败: {e}")
        return None


# 测试代码
if __name__ == "__main__":
    def test():
        # 测试订单ID
        test_order_id = "2856024697612814489"
        
        print(f"🔍 开始使用API获取订单详情: {test_order_id}")
        
        result = fetch_order_detail_api_sync(test_order_id)
        
        if result:
            print("✅ 订单详情获取成功:")
            print(f"📋 订单ID: {result['order_id']}")
            print(f"🌐 URL: {result['url']}")
            print(f"📄 页面标题: {result['title']}")
            print(f"🛍️ 规格名称: {result.get('spec_name', '未获取到')}")
            print(f"📝 规格值: {result.get('spec_value', '未获取到')}")
            print(f"🔢 数量: {result.get('quantity', '未获取到')}")
            print(f"💰 金额: {result.get('amount', '未获取到')}")
            print(f"👤 买家昵称: {result.get('buyer_nickName', '未获取到')}")
            print(f"📞 买家电话: {result.get('buyer_phone', '未获取到')}")
            print(f"📍 买家地址: {result.get('buyer_address', '未获取到')}")
        else:
            print("❌ 订单详情获取失败")
    
    # 运行测试
    test()
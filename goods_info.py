import json
import re
import sys

import frida
import loguru

from util.db.sql_utils import getdb

loguru.logger.add("error.log", format="{time} {level} {message}", level="ERROR")
jscode = """

Java.perform(
    function () {
        var Aegon = Java.use('com.kuaishou.aegon.Aegon');
        Aegon.nativeUpdateConfig.implementation = function (a,b) {
                    a = '{"enable_quic":false,"preconnect_num_streams":2,"quic_idle_timeout_sec":180,"quic_use_bbr":true,"altsvc_broken_time_max":600,"altsvc_broken_time_base":60,"proxy_host_blacklist":[]}';
                    return this.nativeUpdateConfig(a,b);
        }
    }
);

Java.perform(function() {
    var RealCall = Java.use('okhttp3.RealCall');
    var ResponseBody = Java.use('okhttp3.ResponseBody');
    var Buffer = Java.use('okio.b');
    
    RealCall.getResponseWithInterceptorChain.implementation = function() {
        var response = this.getResponseWithInterceptorChain();
        
        var request = this.request();
        var url = request.url().encodedPath();
        
        if (url.startsWith("/rest/tp/item/sku/getItemDetailPoiInfo") || url.startsWith("/rest/op/vc/distribution/item/itemDetail")) {
            var requestBodyString = null;
            
            // 获取请求体
            var requestBody = request.body();
            if (requestBody) {
                var buffer = Buffer.$new();
                requestBody.writeTo(buffer);
                requestBodyString = buffer.readUtf8();
            }
            
            // 处理响应体
            var responseBody = response.body();
            var contentType = responseBody.contentType();
            var responseBodyString = responseBody.string();
            
            // 组装成json格式
            var jsonOutput = {
                url: url,
                requestBody: requestBodyString,
                responseBody: responseBodyString
            };
            
            send(JSON.stringify(jsonOutput));
            
            // 创建新的响应体以避免影响原始响应
            var newResponseBody = ResponseBody.create(contentType, responseBodyString);
            return response.newBuilder().body(newResponseBody).build();
        } else {
            return response;
        }
    };
});






"""

db = getdb()
video_goods_list = db.fetchall(
    f'select goods_id from video_goods')
video_goods_ids = []
for goods_id in video_goods_list:
    video_goods_ids.append(goods_id['goods_id'])
goods_map = {}


def on_message(message, data):
    if message['type'] == 'send':
        json_res = json.loads(message['payload'])
        if json_res['url'].startswith('/rest/tp/item/sku/getItemDetailPoiInfo'):
            request_body = json.loads(json_res['requestBody'])
            item_id = request_body['itemId']
            if str(item_id) in video_goods_ids:
                loguru.logger.info(f"商品已存在{item_id}")
            else:
                pois = json.loads(json_res['responseBody'])['data']
                brand_base = re.split(r'[（(]', pois['poiInfo']['poiName'], 1)[0]
                brand = pois['poiInfo']['poiName']
                lng = pois['poiInfo']['longitude']
                lat = pois['poiInfo']['latitude']
                if str(item_id) in goods_map:
                    ins_sql = goods_map[item_id]
                    db.execute(ins_sql, (brand_base, brand, lng, lat))
                    video_goods_ids.append(str(item_id))
                    del goods_map[item_id]
                else:
                    goods_map[item_id] = (
                        f"INSERT INTO `video_goods`(`goods_id`, `goods_name`, `goods_title`, `goods_des`, `commission_rate`, `real_price`, `goods_price`, `sales_volume`, `brand_base`, `brand`, `sales_script`, `top_sales_script`, `type`, `lng`, `lat`, `tips`) VALUES "
                        f"(%s,%s,%s,%s,%s,%s,%s,%s,'{brand_base}','{brand}',null,'刷到先囤  不用可退  到期自动退',1,{lng},{lat},%s)")

        elif json_res['url'].startswith('/rest/op/vc/distribution/item/itemDetail'):
            goods = json.loads(json_res['responseBody'])['data']
            item_id = goods['itemId']
            if str(item_id) in video_goods_ids:
                loguru.logger.info(f"商品已存在{goods['itemTitle']}")
            else:
                loguru.logger.info(f"新增商品{goods['itemTitle']}")
                sale_price = goods['salePrice'] / 100
                market_price = goods['marketPrice'] / 100
                tips = ''
                for example_video in goods['exampleVideos']:
                    if example_video['videoType'] == 1:
                        tips += '#' + example_video['photoTitle'].split('#', 1)[1] if '#' in example_video[
                            'photoTitle'] else ""
                print(goods)
                goods_des = None
                goods_items = None
                if 'groups' in goods['skuDetailList'][0]['itemSkuSetMealDetail']:
                    goods_items = goods['skuDetailList'][0]['itemSkuSetMealDetail']['groups'][0]
                print(goods_items)
                if goods_items is not None and len(goods_items['setMealContents']) > 1:
                    goods_des = f"套餐包含{goods_items['title']},"
                    if goods_items['fromNum'] != goods_items['selectNum']:
                        goods_des += f"{goods_items['fromNum']} 选 {goods_items['selectNum']}"
                    for meal_contents in goods_items['setMealContents']:
                        goods_des += f"{meal_contents['title']}{meal_contents['count']}份,"
                if goods_des is None:
                    goods_meal = goods['skuDetailList'][0]['itemSkuSetMealDetail']
                    if 'remark' in goods_meal:
                        goods_remark = goods_meal['remark']
                        print(goods_remark)
                        if goods_remark != '' and '套餐内容' in goods_remark:
                            goods_des = goods_remark.split('\n', 1)[0]
                            goods_des = goods_des.replace('套餐内容：', '套餐包含').replace('套餐内容', '套餐包含')
                            print(goods_des)
                item_title = (goods['itemTitle'].replace('shakeshake（自动发券到小程序）', '')
                              .replace('（自动发券到小程序）', '')
                              .replace('【券自动发小程序使用】', ''))
                photo_commission = goods['photoCommission']
                sale_volume = goods['saleVolume']
                if item_id in goods_map:
                    ins_sql = goods_map[item_id]
                    db.execute(ins_sql, (item_id, item_title, item_title,
                                         goods_des,
                                         photo_commission, sale_price, market_price,
                                         sale_volume, tips))
                    video_goods_ids.append(str(item_id))
                    del goods_map[item_id]
                else:
                    goods_map[item_id] = (
                        f"INSERT INTO `video_goods`(`goods_id`, `goods_name`, `goods_title`, `goods_des`, `commission_rate`, `real_price`, `goods_price`, `sales_volume`, `brand_base`, `brand`, `sales_script`, `top_sales_script`, `type`, `lng`, `lat`, `tips`) VALUES "
                        f"({item_id},'{item_title}','{item_title}','{goods_des}',{photo_commission},{sale_price},{market_price},{sale_volume},%s,%s,null,'刷到先囤  不用可退  到期自动退',1,%s,%s,'{tips}')")

    else:
        loguru.logger.info(message)


process = frida.get_remote_device()

# pid = process.spawn(['com.kuaishou.nebula']) #  极速
pid = process.spawn(['com.smile.gifmaker'])  # app
session = process.attach(pid)
script = session.create_script(jscode)
script.on('message', on_message)
script.load()
process.resume(pid)
sys.stdin.read()

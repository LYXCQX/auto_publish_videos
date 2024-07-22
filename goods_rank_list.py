import json
import os
import re

import frida, sys

from util.db.sql_utils import getdb

jscode = """

Java.perform(function() {
    var RealCall = Java.use('okhttp3.RealCall');
    var ResponseBody = Java.use('okhttp3.ResponseBody');

    RealCall.getResponseWithInterceptorChain.implementation = function() {
        var response = this.getResponseWithInterceptorChain();

        var request = this.request();
        var url = request.url().encodedPath();
        if (url.startsWith("/rest/merchant/apicenter/distribution/distributor/pool/rank/list")) {
            var responseBody = response.body();
            var contentType = responseBody.contentType();
            var responseBodyString = responseBody.string();
            send(responseBodyString);
            // Create a new response body to avoid affecting the original response
            var newResponseBody = ResponseBody.create(contentType, responseBodyString);
            return response.newBuilder().body(newResponseBody).build();
        } else {
            return response;
        }
    };
});





"""

flist = []
db = getdb()
video_goods_ids = db.fetchall(
    f'select goods_id from video_goods')
def on_message(message, data):
    if message['type'] == 'send':
        # print("[*] {0}".format(message['payload']))
        flist.append(message['payload'])
        goods = message['payload']
        goods = json.loads(goods)
        for good in goods['data']['pools']:
            if good['itemId'] in video_goods_ids:
                print(f"商品已存在{good['itemTitle']}")
            else:
                print(f"新增商品{good['itemTitle']}")
                db.execute(
                    f"INSERT INTO `video_goods`(`goods_id`, `goods_name`, `goods_title`, `goods_des`, `commission_rate`, `real_price`, `goods_price`, `sales_volume`, `brand_base`, `brand`, `sales_script`, `top_sales_script`, `type`, `lng`, `lat`) "
                    f"VALUES ({good['itemId']},'{good['itemTitle']}','{good['itemTitle']}',null,{good['commission']},{good['salePrice']},{good['marketPrice']},{good['saleVolume']},'{re.split(r'[（(]', good['poiInfo']['poiName'], 1)[0]}','{good['poiInfo']['poiName']}',null,'刷到先囤 不用可退 到期自动退',1,{good['poiInfo']['longitude']},{good['poiInfo']['latitude']})")

    else:
        print(message)


process = frida.get_remote_device()

# pid = process.spawn(['com.kuaishou.nebula']) #  极速
pid = process.spawn(['com.smile.gifmaker'])  # app
session = process.attach(pid)
script = session.create_script(jscode)
script.on('message', on_message)
script.load()
process.resume(pid)
sys.stdin.read()

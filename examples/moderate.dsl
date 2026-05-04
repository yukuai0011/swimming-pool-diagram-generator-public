swimlaneDiagram
title 中等复杂度示例

lane sales "销售部"
lane warehouse "仓库"
lane logistics "物流"

node order in sales process "接收订单"
node check in warehouse decision "库存检查"
node pack in warehouse process "打包"
node ship in logistics process "发货"
node deliver in logistics process "配送"
node confirm in sales [start/end] "确认收货"

connect order --> check
connect check -->|有货| pack
connect check -->|缺货| order : 等待补货
connect pack --> ship
connect ship --> deliver
connect deliver --> confirm

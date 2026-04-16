swimlaneDiagram
title 售后退货处理（复杂示例：跨泳道与交叉线）

lane partner "合作服务商"
lane aftersales "售后部"
lane logistics "物流部"
lane warehouse "仓库部"
lane sales "销售部"
lane finance "财务部"

node start in partner [start/end] "开始"
node receive in partner process "接收退机并登记"
node triage in aftersales decision "资料是否完整"
node reject in partner process "驳回并补充资料"
node classify in aftersales decision "是否可修"
node reserve in warehouse data "预占备件库存"
node purchase in sales subprocess "发起紧急采购"
node repair in logistics subprocess "执行维修"
node qa in aftersales decision "质检是否通过"
node repack in warehouse process "重新包装"
node ship in logistics process "安排返还运输"
node sales_order in sales document "创建 Sales Order"
node invoice in finance document "开票"
node refund in finance process "退款/冲销"
node close in partner [start/end] "流程关闭"

connect start --> receive
connect receive --> triage
connect triage -->|不完整| reject
connect reject --> receive : 补件后重提
connect triage -->|完整| classify
connect classify -->|可修| repair
connect classify -->|不可修| refund
connect repair --> qa
connect qa --> repair : 失败-返修
connect qa -->|通过| reserve
connect reserve -->|有库存| repack
connect reserve -->|无库存| purchase
connect purchase --> reserve : 到货回写
connect repack --> ship
connect ship --> sales_order
connect sales_order --> invoice
connect invoice --> close
connect refund --> close
connect purchase --> invoice : 费用确认
connect repack --> invoice : 物流费用
connect classify --> sales_order : 先建单预留

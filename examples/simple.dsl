swimlaneDiagram
title 简单示例

lane a "部门A"
lane b "部门B"

node start in a [start/end] "开始"
node process in a process "处理"
node decision in b decision "审核"
node end in b [start/end] "结束"

connect start --> process
connect process --> decision
connect decision -->|通过| end
connect decision -->|拒绝| process

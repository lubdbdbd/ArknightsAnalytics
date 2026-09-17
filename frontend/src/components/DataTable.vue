<script setup>
import { computed, ref } from 'vue'
const props = defineProps({ rows: { type: Array, default: () => [] }, columns: Array, action: String })
defineEmits(['select'])
const sort = ref(''), ascending = ref(true)
const sorted = computed(() => !sort.value ? props.rows : [...props.rows].sort((first,second) => {
 const left = first[sort.value], right = second[sort.value]
 return (typeof left === 'number' && typeof right === 'number' ? left-right : String(left??'').localeCompare(String(right??''),'zh-CN')) * (ascending.value?1:-1)
}))
function reorder(key) { ascending.value = sort.value===key?!ascending.value:true; sort.value=key }
const names={paid:'已支付',cancelled:'已取消',delivered:'已签收',shipped:'已发货',pending:'待核验',verified:'已核验',rejected:'已驳回',active:'在售',inactive:'停售',planned:'规划中',closed:'已关闭',refund:'退款',return:'退货',exchange:'换货'}
function display(value, column) {
 if (value===null||value===undefined||value==='') return '—'
 if (column.type==='money') return '¥'+Number(value).toLocaleString('zh-CN',{maximumFractionDigits:2,minimumFractionDigits:2})
 if (column.type==='percent') return (Number(value)*100).toFixed(1)+'%'
 if (column.type==='number') return Number(value).toLocaleString('zh-CN',{maximumFractionDigits:1})
 return names[value]||value
}
</script>
<template><div class="table-wrap"><table><thead><tr><th v-for="column in columns" :key="column.key"><button @click="reorder(column.key)">{{ column.label }}<span class="sort-arrow">{{ sort===column.key?(ascending?'↑':'↓'):'↕' }}</span></button></th><th v-if="action">操作</th></tr></thead>
<tbody><tr v-for="(row,index) in sorted" :key="row.entity_id||row.case_id||row.order_line_id||row.order_id||index"><td v-for="column in columns" :key="column.key" :class="[{ numeric: ['money','number','percent'].includes(column.type) }, column.class]" :title="String(row[column.key]??'')"><span v-if="column.type==='badge'" class="badge" :class="{'amber': /pending|P1|P0|未|需|待/.test(String(row[column.key])), 'gray': row[column.key]==='inactive', 'red':row[column.key]==='rejected'}">{{ display(row[column.key],column) }}</span><template v-else>{{ display(row[column.key],column) }}</template></td><td v-if="action"><button class="table-action" @click="$emit('select',row)">{{ action }} ↗</button></td></tr></tbody></table><div v-if="!rows.length" class="empty">没有匹配的记录，请调整筛选条件。</div></div></template>

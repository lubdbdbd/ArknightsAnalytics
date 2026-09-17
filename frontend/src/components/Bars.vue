<script setup>
import { computed } from 'vue'
const props = defineProps({ rows: { type: Array, default: () => [] }, label: String, value: String, suffix: { type: String, default: '' }, percent: Boolean })
const maximum = computed(() => Math.max(...props.rows.map(row => Number(row[props.value]) || 0), 1))
const format = value => props.percent ? (value*100).toFixed(1)+'%' : Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 0 })+props.suffix
</script>
<template><div class="bars"><div class="bar-row" v-for="(row,index) in rows" :key="row[label]"><div class="bar-label"><span><small>{{ String(index+1).padStart(2,'0') }}</small>{{ row[label] }}</span><b>{{ format(row[value]) }}</b></div><div class="bar-track"><i :style="{width:(Number(row[value])||0)/maximum*100+'%',background:index===0?'#16846d':index===1?'#54a28b':'#9ac5b5'}"></i></div></div><p v-if="!rows.length" class="empty">当前没有可展示的数据</p></div></template>

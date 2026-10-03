<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const lanes = ref<any[]>([])
onMounted(async () => { lanes.value = (await api('/refills/full?location_id=1')).lanes })
</script>
<template>
  <h1>满仓</h1>
  <p class="sub">仅列库存加在途恰好等于容量（缺口为 0）的满仓货道；库存加在途大于容量的超占货道不在此页</p>
  <div class="card">
    <table>
      <thead><tr><th>货道</th><th>商品</th><th>库存</th><th>在途</th><th>容量</th><th>状态</th></tr></thead>
      <tbody>
        <tr v-for="l in lanes" :key="l.lane_id">
          <td>{{ l.slot_no }}</td><td>{{ l.sku_name }}</td><td>{{ l.stock }}</td><td>{{ l.in_transit }}</td><td>{{ l.capacity }}</td>
          <td><span class="badge badge-ok">满仓</span></td>
        </tr>
        <tr v-if="!lanes.length"><td colspan="6" class="muted">当前没有满仓货道</td></tr>
      </tbody>
    </table>
  </div>
</template>

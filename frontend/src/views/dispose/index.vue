<template>
  <section class="page" data-module="dispose">
    <header class="page-head">
      <div>
        <h2>故障处置管理</h2>
        <p class="page-desc">维护处置单，围绕处置单号、关联故障、处置措施、更换器材做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记处置单</button>
        <button class="btn" type="button" @click="exportRows">导出故障处置清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <div class="identity-bar">
      <label class="filter-item">
        <span>当前账号</span>
        <input v-model="session.operator" placeholder="登录账号，如：验收员丙" />
      </label>
      <label class="filter-item">
        <span>所属工区</span>
        <input v-model="session.section" placeholder="账号所属工区，如：信号一工区" />
      </label>
      <span class="identity-hint">验收环节仅验收人员且属本工区的账号可提交，其余账号只读可见</span>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              :disabled="actionDisabled(action, row)"
              :title="actionHint(action, row)"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无故障处置数据，可先登记处置单</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条故障处置记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/dispose'
const columns = ["处置单号", "关联故障", "处置措施", "更换器材", "处置人员", "完成时间", "验收人员", "所属工区", "处置状态"]
const actions = ["受理处置", "提交验收", "确认验收"]
const statuses = ["待受理", "处置中", "待验收", "已验收"]
const stats = [{"label": "待受理处置", "value": 0}, {"label": "处置中单据", "value": 0}, {"label": "本月验收单数", "value": 0}]

const session = useSessionStore()
const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '处置单登记入口尚未接入审批流'
}

// 受理处置照旧不做限制；提交验收、确认验收按状态与归属约束，不满足时按钮置灰并给出原因
function actionDisabled(action: string, row: Row): boolean {
  if (action === '受理处置') return false
  if (action === '提交验收') {
    if (row['处置状态'] !== '处置中') return true
    return Boolean(row['所属工区']) && session.section !== row['所属工区']
  }
  if (row['处置状态'] !== '待验收') return true
  return session.operator !== row['验收人员'] || session.section !== row['所属工区']
}

function actionHint(action: string, row: Row): string {
  if (action === '受理处置') return ''
  if (action === '提交验收') {
    if (row['处置状态'] !== '处置中') return `当前状态为「${row['处置状态'] ?? '未知'}」，不能提交验收`
    if (row['所属工区'] && session.section !== row['所属工区']) return `仅所属工区「${row['所属工区']}」的账号可提交验收`
    return ''
  }
  if (row['处置状态'] !== '待验收') return `当前状态为「${row['处置状态'] ?? '未知'}」，不能确认验收`
  if (session.operator !== row['验收人员']) return `仅验收人员「${row['验收人员']}」可确认验收`
  if (session.section !== row['所属工区']) return `仅所属工区「${row['所属工区']}」的账号可确认验收`
  return ''
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({
        values: { action, 操作人: session.operator, 操作工区: session.section },
      }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message ?? payload?.detail ?? '故障处置动作未生效，请稍后重试')
    }
    noticeMessage.value = String(payload.message ?? '')
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '故障处置操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('处置单列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '处置单列表读取失败'
  }
}

onMounted(reload)
</script>

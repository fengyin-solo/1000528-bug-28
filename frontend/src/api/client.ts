/** 统一请求封装：拼后端地址、带当前账号、抛网络错误、给页脚留一句可读的说明。 */
import { OPERATOR_STORAGE_KEY } from '@/stores/session'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

export function request(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  const operator = localStorage.getItem(OPERATOR_STORAGE_KEY) ?? '值班管理员'
  return fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      // 账号名是中文，请求头只能放 ASCII，先编码、后端再解码
      'X-Operator': encodeURIComponent(operator),
      ...(init?.headers ?? {}),
    },
  }).catch((error: unknown) => {
    const detail = error instanceof Error ? error.message : '请求未送达'
    throw new Error(`接口请求失败：${detail}`)
  })
}

export async function fetchJson<T>(path: string): Promise<T> {
  const response = await request(path)
  if (!response.ok) {
    throw new Error(`接口返回 ${response.status}，数据未更新`)
  }
  return (await response.json()) as T
}

<template>
  <div class="chat-container">
    <!-- 顶部导航栏 -->
    <header class="chat-header">
      <div class="logo">
        <span class="logo-icon">📊</span>
        <h1>Data Agent Pro</h1>
      </div>
      <div class="subtitle">智能数据查询助手</div>
    </header>

    <!-- 消息区 -->
    <main ref="messagesEl" class="messages-area">
      <div class="messages-inner">
        <div
            v-for="(msg, index) in messages"
            :key="index"
            :class="['message-wrapper', msg.role]"
        >
          <div v-if="msg.role === 'assistant'" class="avatar bot-avatar">
            <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round">
              <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/>
            </svg>
          </div>

          <div class="message-content">
            <!-- 文本 -->
            <div v-if="msg.type === 'text'" class="message-bubble text-bubble">
              {{ msg.content }}
            </div>

            <!-- 进度步骤 -->
            <div v-else-if="msg.type === 'steps'" class="message-bubble steps-bubble">
              <div class="steps-header">正在思考及执行中...</div>
              <div v-for="(step, sIdx) in msg.steps" :key="sIdx" class="step-item">
                <span class="status-indicator" :class="step.status">
                  <i v-if="step.status === 'running'" class="icon-loading"></i>
                  <i v-else-if="step.status === 'success'" class="icon-success">✓</i>
                  <i v-else-if="step.status === 'error'" class="icon-error">✗</i>
                </span>
                <span class="step-text" :class="{'step-done': step.status === 'success'}">{{ step.text }}</span>
              </div>
            </div>

            <!-- 表格 -->
            <div v-else-if="msg.type === 'table'" class="message-bubble table-bubble">
              <div class="table-container">
                <table class="data-table">
                  <thead>
                  <tr>
                    <th v-for="col in msg.columns" :key="col">{{ col }}</th>
                  </tr>
                  </thead>
                  <tbody>
                  <tr v-for="(row, rIdx) in msg.rows" :key="rIdx">
                    <td v-for="col in msg.columns" :key="col">{{ row[col] }}</td>
                  </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <!-- 错误 -->
            <div v-else-if="msg.type === 'error'" class="message-bubble error-bubble">
              <span class="error-icon">⚠️</span>
              {{ msg.content }}
            </div>
          </div>

          <div v-if="msg.role === 'user'" class="avatar user-avatar">
            <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round">
              <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"></path>
              <circle cx="12" cy="7" r="4"></circle>
            </svg>
          </div>
        </div>
        <!-- Welcome Message if empty -->
        <div v-if="messages.length === 0" class="welcome-screen">
          <h2>你好，我是 Data Agent Pro</h2>
          <p>你可以问我关于数据的任何问题，例如：“查询上个月的销售额”、“统计各省份的用户分布”等。</p>
        </div>
        <div class="messages-bottom-spacer"></div>
      </div>
    </main>

    <!-- 底部输入区 -->
    <footer class="input-area">
      <div class="input-container">
        <input
            v-model="question"
            @keyup.enter="sendQuestion"
            placeholder="随时向我提问..."
            :disabled="loading"
        />
        <button class="send-btn" @click="sendQuestion" :disabled="loading || !question.trim()">
          <span v-if="loading">分析中</span>
          <span v-else>发送请求</span>
        </button>
      </div>
    </footer>
  </div>
</template>

<script setup>
import {nextTick, ref} from "vue";

const API_URL = "/api/query";

const question = ref("");
const loading = ref(false);
const messages = ref([]);
const messagesEl = ref(null);

function scrollToBottom() {
  const el = messagesEl.value;
  if (!el) return;
  el.scrollTop = el.scrollHeight;
}

async function sendQuestion() {
  if (!question.value || loading.value) return;

  const q = question.value;
  question.value = "";
  loading.value = true;

  messages.value.push({role: "user", type: "text", content: q});

  // steps 容器
  const stepIndex =
      messages.value.push({
        role: "assistant",
        type: "steps",
        steps: [],
      }) - 1;

  await nextTick();
  scrollToBottom();

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({query: q}),
    });

    if (!response.body) throw new Error("服务器未返回流");

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const {value, done} = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, {stream: true});
      const events = buffer.split("\n\n");
      buffer = events.pop();

      for (const evt of events) {
        const line = evt.trim();
        if (!line.startsWith("data:")) continue;

        let data;
        try {
          data = JSON.parse(line.replace(/^data:\s*/, ""));
        } catch {
          continue;
        }

        const steps = messages.value[stepIndex].steps;

        // ✅ progress：完全按后端状态渲染
        if (data.type === "progress") {
          let step = steps.find((s) => s.text === data.step);

          if (!step) {
            step = {
              text: data.step,
              status: data.status,
            };
            steps.push(step);
          } else {
            step.status = data.status;
          }
        }

        // ✅ 表格结果
        else if (data.type === "result" && Array.isArray(data.data)) {
          messages.value.push({
            role: "assistant",
            type: "table",
            columns: Object.keys(data.data[0] || {}),
            rows: data.data,
          });
        }

        // ✅ 错误
        else if (data.type === "error") {
          messages.value.push({
            role: "assistant",
            type: "error",
            content: data.message || "发生错误",
          });
        }

        await nextTick();
        scrollToBottom();
      }
    }
  } catch (e) {
    messages.value.push({
      role: "assistant",
      type: "error",
      content: e?.message || "请求失败",
    });
  } finally {
    loading.value = false;
    await nextTick();
    scrollToBottom();
  }
}
</script>
<style scoped>
:global(html),
:global(body) {
  height: 100%;
  margin: 0;
  background-color: #f3f4f6;
  font-family: 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

:global(#app) {
  height: 100%;
  max-width: none !important;
  margin: 0 !important;
  padding: 0 !important;
}

/* 整体容器 */
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100%;
  margin: 0;
  background: #ffffff;
}

/* 顶部导航栏 */
.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background-color: #ffffff;
  border-bottom: 1px solid #e5e7eb;
  z-index: 10;
}

.chat-header .logo {
  display: flex;
  align-items: center;
  gap: 12px;
}

.chat-header .logo-icon {
  font-size: 24px;
}

.chat-header h1 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #111827;
  letter-spacing: 0.5px;
}

.chat-header .subtitle {
  font-size: 14px;
  color: #6b7280;
  background: #f3f4f6;
  padding: 4px 12px;
  border-radius: 12px;
}

/* 欢迎页 */
.welcome-screen {
  text-align: center;
  margin: auto;
  padding: 40px 20px;
  color: #374151;
}

.welcome-screen h2 {
  font-size: 24px;
  margin-bottom: 12px;
  font-weight: 600;
  color: #111827;
}

.welcome-screen p {
  font-size: 15px;
  color: #6b7280;
  line-height: 1.6;
}

/* 消息区 */
.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  scroll-behavior: smooth;
  background-color: #f9fafb;
}

.messages-inner {
  width: 100%;
  max-width: 850px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
}

.message-wrapper {
  display: flex;
  margin-bottom: 24px;
  align-items: flex-start;
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.message-wrapper.assistant {
  justify-content: flex-start;
}

.message-wrapper.user {
  justify-content: flex-end;
}

.avatar {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #4f46e5;
  flex-shrink: 0;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.bot-avatar {
  background: #e0e7ff;
  color: #3730a3;
  margin-right: 12px;
}

.user-avatar {
  background: #dbeafe;
  color: #1e40af;
  margin-left: 12px;
}

.message-content {
  max-width: 75%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.message-wrapper.user .message-content {
  align-items: flex-end;
}

/* 消息气泡 */
.message-bubble {
  padding: 14px 18px;
  border-radius: 14px;
  font-size: 15px;
  line-height: 1.6;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}

.text-bubble {
  background: #ffffff;
  color: #1f2937;
  border: 1px solid #e5e7eb;
}

.message-wrapper.user .text-bubble {
  background: #3b82f6;
  color: #ffffff;
  border: none;
  border-radius: 14px 2px 14px 14px;
}

.message-wrapper.assistant .text-bubble {
  border-radius: 2px 14px 14px 14px;
}

/* 步骤块 */
.steps-bubble {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  width: 100%;
}

.steps-header {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e2e8f0;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  font-size: 14px;
}

.step-item:last-child {
  margin-bottom: 0;
}

.status-indicator {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  font-size: 12px;
}

.status-indicator.running {
  color: #d97706;
}

.icon-loading {
  display: block;
  width: 14px;
  height: 14px;
  border: 2px solid #fcd34d;
  border-top-color: #d97706;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.status-indicator.success {
  color: #059669;
  background: #d1fae5;
}

.status-indicator.error {
  color: #dc2626;
  background: #fee2e2;
}

.step-text {
  color: #334155;
  transition: color 0.3s;
}

.step-text.step-done {
  color: #64748b;
}

/* 表格块 */
.table-bubble {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  padding: 0;
  overflow: hidden;
  width: 100%;
}

.table-container {
  overflow-x: auto;
  max-width: 100%;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}

.data-table th,
.data-table td {
  padding: 10px 16px;
  border-bottom: 1px solid #e5e7eb;
  font-size: 14px;
  color: #374151;
  white-space: nowrap;
}

.data-table th {
  background-color: #f9fafb;
  font-weight: 600;
  color: #111827;
  position: sticky;
  top: 0;
  border-bottom: 2px solid #e5e7eb;
}

.data-table tr:last-child td {
  border-bottom: none;
}

.data-table tbody tr:hover {
  background-color: #f3f4f6;
}

/* 错误块 */
.error-bubble {
  background: #fef2f2;
  color: #991b1b;
  border: 1px solid #fecaca;
  display: flex;
  align-items: center;
  gap: 8px;
}

.error-icon {
  font-size: 16px;
}

/* 底部留白 */
.messages-bottom-spacer {
  height: 20px;
}

/* 底部输入区 */
.input-area {
  padding: 20px 24px;
  background-color: #ffffff;
  border-top: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.input-container {
  display: flex;
  align-items: center;
  width: 100%;
  max-width: 800px;
  background: #ffffff;
  border: 1px solid #d1d5db;
  border-radius: 24px;
  padding: 6px 6px 6px 20px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
  transition: border-color 0.3s, box-shadow 0.3s;
}

.input-container:focus-within {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
}

.input-container input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 15px;
  color: #1f2937;
  background: transparent;
}

.input-container input::placeholder {
  color: #9ca3af;
}

.send-btn {
  background: #3b82f6;
  color: #ffffff;
  border: none;
  border-radius: 20px;
  padding: 8px 20px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.send-btn:hover:not(:disabled) {
  background: #2563eb;
}

.send-btn:disabled {
  background: #9ca3af;
  cursor: not-allowed;
}
</style>

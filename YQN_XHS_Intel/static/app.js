const state = {
  task: "material",
  estimate: null,
  settings: null,
};

const STORAGE_KEYS = {
  apiKey: "yqn_tikhub_api_key",
  apiBase: "yqn_tikhub_api_base",
};

const $ = (id) => document.getElementById(id);

function log(message) {
  const box = $("logBox");
  const time = new Date().toLocaleTimeString("zh-CN", { hour12: false });
  box.textContent = `[${time}] ${message}\n` + box.textContent;
}

async function apiGet(url) {
  const resp = await fetch(url);
  const data = await resp.json();
  if (!resp.ok || data.ok === false) throw new Error(data.message || "请求失败");
  return data;
}

async function apiPost(url, payload) {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await resp.json();
  if (!resp.ok || data.ok === false) throw new Error(data.message || "请求失败");
  return data;
}

function storedApiKey() {
  return localStorage.getItem(STORAGE_KEYS.apiKey) || "";
}

function storedApiBase() {
  return localStorage.getItem(STORAGE_KEYS.apiBase) || "https://api.tikhub.io";
}

function apiKeyPreview(apiKey) {
  if (!apiKey) return "";
  if (apiKey.length <= 8) return "*".repeat(apiKey.length);
  return `${apiKey.slice(0, 4)}${"*".repeat(Math.max(4, apiKey.length - 8))}${apiKey.slice(-4)}`;
}

function payload(options = {}) {
  const data = {
    task: state.task,
    keyword: $("keyword").value.trim() || "墨西哥海外仓",
    quantity: Number($("quantity").value || 3),
    maxCalls: Number($("maxCalls").value || 30),
    maxCost: Number($("maxCost").value || 0.05),
    testMode: $("testMode").checked,
    apiBase: $("apiBase").value || storedApiBase(),
  };
  if (options.includeApiKey) {
    data.apiKey = storedApiKey();
  }
  return data;
}

function money(value) {
  return `$${Number(value || 0).toFixed(2)}`;
}

function renderSettings(settings) {
  const localKey = storedApiKey();
  const localBase = storedApiBase();
  state.settings = {
    ...settings,
    hasApiKey: Boolean(localKey),
    apiKeyPreview: apiKeyPreview(localKey),
    apiBase: localBase,
  };
  $("keyStatus").textContent = localKey
    ? `当前浏览器已保存 API Key：${apiKeyPreview(localKey)}。现在可以先估算费用，再确认真实运行。`
    : "未填写 API Key：现在只能生成演示 Excel，不会真实调用 TikHub。";
  $("apiBase").value = localBase;
  $("connectionResult").textContent = localKey
    ? `当前浏览器已保存：${apiKeyPreview(localKey)}`
    : "填写后可以先测试连接。";
  $("configPath").textContent = "朋友模式：API Key 只保存在当前浏览器，不写入服务器文件。";
}

function renderEstimate(estimate) {
  state.estimate = estimate;
  $("plannedCalls").textContent = estimate.plannedCalls;
  $("plannedCost").textContent = money(estimate.plannedCost);
  $("runButton").disabled = false;
  const limits = estimate.limitedBy.length
    ? `<div class="notice-text">${estimate.limitedBy.join("；")}</div>`
    : `<div class="notice-text">未超过本次保护上限。</div>`;
  const items = estimate.steps
    .map((step) => `<li><span>${step.name} × ${step.count}</span><strong>${money(step.cost)}</strong></li>`)
    .join("");
  $("estimateBox").innerHTML = `
    <strong>${estimate.taskName}</strong>
    <div class="notice-text">这不是马上扣钱，只是先告诉你：如果点击确认运行，大概要按下面这些 API 按钮。</div>
    <ul class="estimate-list">${items}</ul>
    ${limits}
    <div class="notice-text">${estimate.priceMessage}</div>
  `;
  log(`已估算：${estimate.plannedCalls} 次，预计 ${money(estimate.plannedCost)}。`);
}

async function loadSettings() {
  try {
    const data = await apiGet("/api/settings");
    renderSettings(data);
  } catch (err) {
    log(`读取设置失败：${err.message}`);
  }
}

async function estimate() {
  $("runButton").disabled = true;
  $("outputBox").innerHTML = "";
  log("正在查询接口单价并估算费用...");
  try {
    const data = await apiPost("/api/estimate", payload());
    renderEstimate(data.estimate);
  } catch (err) {
    log(`估算失败：${err.message}`);
  }
}

async function runTask() {
  if (!state.estimate) {
    await estimate();
  }
  $("runButton").disabled = true;
  $("estimateButton").disabled = true;
  $("outputBox").innerHTML = "";
  log("已确认运行，开始处理...");
  try {
    const data = await apiPost("/api/run", payload({ includeApiKey: true }));
    $("actualCalls").textContent = data.paidCalls;
    $("actualCost").textContent = money(data.spent);
    const notes = data.messages.length ? data.messages.map((item) => `<div>${item}</div>`).join("") : "<div>运行完成。</div>";
    $("outputBox").innerHTML = `
      <strong>Excel 已生成</strong>
      <div><a href="${data.downloadUrl}">点击下载 / 打开 Excel</a></div>
      <div class="local-path">${data.outputFile}</div>
      ${notes}
    `;
    log(`完成：本次实际付费调用 ${data.paidCalls} 次，花费 ${money(data.spent)}。`);
    log(`Excel：${data.outputFile}`);
  } catch (err) {
    log(`运行失败：${err.message}`);
  } finally {
    $("estimateButton").disabled = false;
    $("runButton").disabled = false;
  }
}

async function saveKey() {
  try {
    const key = $("apiKey").value.trim() || storedApiKey();
    if (!key) throw new Error("请先粘贴 TikHub API Key。");
    localStorage.setItem(STORAGE_KEYS.apiKey, key);
    localStorage.setItem(STORAGE_KEYS.apiBase, $("apiBase").value || "https://api.tikhub.io");
    renderSettings({ apiBase: storedApiBase() });
    $("apiKey").value = "";
    $("settingsDialog").close();
    log("API Key 已保存到当前浏览器。");
  } catch (err) {
    log(`保存失败：${err.message}`);
  }
}

async function clearKey() {
  try {
    localStorage.removeItem(STORAGE_KEYS.apiKey);
    localStorage.setItem(STORAGE_KEYS.apiBase, $("apiBase").value || "https://api.tikhub.io");
    renderSettings({ apiBase: storedApiBase() });
    $("apiKey").value = "";
    $("connectionResult").textContent = "API Key 已从当前浏览器清除。";
    log("API Key 已清除。");
  } catch (err) {
    log(`清除失败：${err.message}`);
  }
}

async function checkConnection() {
  const resultBox = $("connectionResult");
  resultBox.textContent = "正在测试连接...";
  try {
    const data = await apiPost("/api/check-connection", {
      apiKey: $("apiKey").value.trim() || storedApiKey(),
      apiBase: $("apiBase").value,
    });
    resultBox.textContent = data.message || "连接成功。";
    log("TikHub API Key 连接成功。");
  } catch (err) {
    resultBox.textContent = err.message || "连接失败，请检查 API Key。";
    log(`TikHub API Key 连接失败：${err.message}`);
  }
}

async function showPrices() {
  log("正在读取当前接口单价...");
  try {
    const data = await apiGet("/api/prices");
    const lines = data.prices.map((item) => `${item.name}：${money(item.unitPrice)}/次`);
    log(`${data.message}\n${lines.join("\n")}`);
  } catch (err) {
    log(`读取单价失败：${err.message}`);
  }
}

function bindEvents() {
  document.querySelectorAll(".task-button").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".task-button").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      state.task = button.dataset.task;
      state.estimate = null;
      $("runButton").disabled = true;
      log(`已选择：${button.textContent.trim()}。`);
    });
  });
  ["keyword", "quantity", "maxCalls", "maxCost", "testMode", "apiBase"].forEach((id) => {
    $(id).addEventListener("change", () => {
      state.estimate = null;
      $("runButton").disabled = true;
    });
  });
  document.querySelectorAll("[data-open-settings]").forEach((button) => {
    button.addEventListener("click", () => $("settingsDialog").showModal());
  });
  $("saveKeyButton").addEventListener("click", saveKey);
  $("clearKeyButton").addEventListener("click", clearKey);
  $("checkKeyButton").addEventListener("click", checkConnection);
  $("estimateButton").addEventListener("click", estimate);
  $("runButton").addEventListener("click", runTask);
  $("pricesButton").addEventListener("click", showPrices);
}

bindEvents();
loadSettings();

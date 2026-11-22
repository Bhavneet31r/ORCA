const form = document.getElementById('queryForm');
const input = document.getElementById('queryInput');
const chatLog = document.getElementById('chatLog');
const statusPill = document.getElementById('statusPill');
const locationSelect = document.getElementById('locationSelect');
const sendButton = document.getElementById('sendButton');

let pendingQuery = null;
let activeRequest = null;

function setStatus(label, state = '') {
  statusPill.className = `connection-status ${state}`.trim();
  statusPill.querySelector('span:last-child').textContent = label;
}

function addText(parent, tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  element.textContent = text;
  parent.append(element);
  return element;
}

function addResultCard(grid, title, className = '') {
  const card = document.createElement('section');
  card.className = `result-card ${className}`.trim();
  addText(card, 'h3', '', title);
  grid.append(card);
  return card;
}

function renderAdvisoryDetails(body, data) {
  const intents = data.intents || [];
  const wants = (name) => intents.includes(name);
  const wantsConditions = wants('CONDITIONS') || wants('SAFETY');

  const grid = document.createElement('div');
  grid.className = 'result-grid';
  body.append(grid);

  const weather = data.weather || {};
  if (wantsConditions) {
    const weatherCard = addResultCard(grid, 'Sea & weather');
    const level = (weather.status || 'UNKNOWN').toLowerCase();
    addText(weatherCard, 'p', `level ${level}`, `Condition level: ${weather.status || 'UNKNOWN'}`);
    addText(weatherCard, 'p', '', `Forecast window: ${weather.time_range || 'not available'}`);
    if (weather.wave !== null && weather.wave !== undefined) addText(weatherCard, 'p', '', `Maximum waves: ${weather.wave} m`);
    if (weather.wind !== null && weather.wind !== undefined) addText(weatherCard, 'p', '', `Peak wind: ${weather.wind} km/h`);
    if (weather.gust !== null && weather.gust !== undefined) addText(weatherCard, 'p', '', `Peak gusts: ${weather.gust} km/h`);
    if (weather.period !== null && weather.period !== undefined) addText(weatherCard, 'p', '', `Average wave period: ${weather.period} s`);
    if (weather.sst !== null && weather.sst !== undefined) addText(weatherCard, 'p', '', `Sea-surface temperature: ${weather.sst} °C`);
    if (weather.rain !== null && weather.rain !== undefined) addText(weatherCard, 'p', '', `Peak rainfall: ${weather.rain} mm/h`);
    addText(weatherCard, 'p', 'message-meta', `Source: ${weather.source || 'not reported'}`);
    if (weather.simulated) addText(weatherCard, 'span', 'data-tag', 'SIMULATED');
  }

  if (wants('PFZ') || wants('OCEAN')) {
    const pfz = data.pfz || {};
    const pfzCard = addResultCard(grid, 'Satellite fishing-zone estimate');
    if (pfz.available === false) {
      addText(pfzCard, 'p', '', pfz.message || 'No official PFZ data is available.');
    } else if (pfz.latitude !== undefined && pfz.longitude !== undefined) {
      addText(pfzCard, 'p', '', `${pfz.distance_km} km ${pfz.direction} · ${pfz.latitude}, ${pfz.longitude}`);
      addText(pfzCard, 'p', '', `Chlorophyll: ${pfz.chl} mg/m³ · SST: ${pfz.sst} °C`);
      addText(pfzCard, 'p', '', `Satellite observation: ${pfz.observation_date || 'date unavailable'}`);
      if (pfz.observation_age_days > 4) {
        addText(pfzCard, 'p', 'data-tag', `OLDER OBSERVATION · ${pfz.observation_age_days} DAYS`);
      }
      addText(pfzCard, 'p', '', `Estimated travel time: ${pfz.estimated_hours_at_8_knots} h at 8 knots`);
      addText(pfzCard, 'p', 'message-meta', 'Satellite indicators are not official fishing or safety advice.');
    } else {
      addText(pfzCard, 'p', '', pfz.message || 'No candidate estimate is available.');
    }
    addText(pfzCard, 'p', 'message-meta', `Source: ${pfz.source || 'not reported'}`);
    if (pfz.simulated) addText(pfzCard, 'span', 'data-tag', 'SYNTHETIC GRID');
  }

  if (wants('GEOFENCE') || wants('ROUTE')) {
    const boundaryCard = addResultCard(grid, 'Nearby boundaries');
    const boundaryItems = [...(data.geofence?.items || [])].sort((left, right) => left.distance_km - right.distance_km);
    if (!boundaryItems.length) {
      addText(boundaryCard, 'p', '', 'No boundary distances are available.');
    } else {
      const list = document.createElement('ul');
      for (const item of boundaryItems) {
        const state = item.inside ? ' · INSIDE' : item.near ? ' · NEAR' : '';
        addText(list, 'li', '', `${item.name}: ${item.distance_km} km${state}`);
      }
      boundaryCard.append(list);
    }
    addText(boundaryCard, 'p', 'message-meta', data.geofence?.message || 'Approximate distances only.');
    addText(boundaryCard, 'span', 'data-tag', 'ILLUSTRATIVE');
  }

  if (wants('ALERTS')) {
    const alertCard = addResultCard(grid, 'Forecast signals', 'alert-card');
    const alerts = weather.alerts || [];
    if (alerts.length) for (const alert of alerts) addText(alertCard, 'p', '', alert);
    else addText(alertCard, 'p', '', 'No automated severe-weather signals detected in this window.');
    addText(alertCard, 'p', 'message-meta', 'These are forecast indicators, not official cyclone or marine warnings.');
  }
}

function appendMessage(role, text, data = null) {
  const message = document.createElement('article');
  message.className = `message ${role}-message`;

  const mark = addText(message, 'div', 'message-mark', role === 'assistant' ? 'O' : 'You');
  mark.setAttribute('aria-hidden', 'true');

  const body = document.createElement('div');
  body.className = 'message-body';
  addText(body, 'p', 'message-author', role === 'assistant' ? 'ORCA' : 'You');
  addText(body, 'p', 'message-text', text);

  if (role === 'assistant' && data?.mode === 'advisory') {
    addText(
      body,
      'p',
      'message-meta',
      `${data.location || 'Location'} · ${data.weather?.source || 'Forecast source unavailable'}${data.data_notice ? ` · ${data.data_notice}` : ''}`
    );
    renderAdvisoryDetails(body, data);
  } else if (role === 'assistant' && data?.mode === 'need_location') {
    addText(body, 'p', 'message-meta', 'Choose a location on the left, or include one in your next message.');
  }

  message.append(body);
  chatLog.append(message);
  message.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function addThinkingIndicator() {
  const message = document.createElement('article');
  message.className = 'message assistant-message thinking-message';
  message.id = 'thinkingMessage';

  const mark = addText(message, 'div', 'message-mark', 'O');
  mark.setAttribute('aria-hidden', 'true');

  const body = document.createElement('div');
  body.className = 'thinking-body';
  addText(body, 'span', 'thinking-dots', 'Thinking');
  const dots = document.createElement('span');
  dots.className = 'thinking-animation';
  dots.setAttribute('aria-hidden', 'true');
  dots.textContent = '•••';
  body.append(dots);
  message.append(body);
  chatLog.append(message);
  message.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  return message;
}

function looksLikeLocationOnly(text) {
  return !/\b(safe|safety|weather|forecast|wave|wind|fishing|fish|boundary|border|protected|alert|cyclone|tide|sst|chlorophyll|route)\b/i.test(text)
    && (text.length < 60 || /-?\d+(?:\.\d+)?\s*[,;]\s*-?\d+(?:\.\d+)?/.test(text));
}

async function sendMessage(query) {
  const text = query.trim();
  if (!text || sendButton.disabled || activeRequest) return;

  const chosenLocation = locationSelect.value;
  let requestQuery = text;
  if (pendingQuery && looksLikeLocationOnly(text)) {
    requestQuery = chosenLocation ? pendingQuery : `${pendingQuery} ${text}`;
  }
  pendingQuery = null;

  const welcome = chatLog.querySelector('.welcome-card');
  if (welcome) welcome.remove();
  appendMessage('user', text);
  input.value = '';
  input.focus();
  sendButton.disabled = true;
  setStatus('Checking', 'busy');
  const thinking = addThinkingIndicator();
  const controller = new AbortController();
  activeRequest = controller;
  sendButton.innerHTML = '<span>Pause</span><span aria-hidden="true">■</span>';
  sendButton.disabled = false;

  try {
    const response = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: requestQuery, location: chosenLocation || null }),
      signal: controller.signal
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);

    appendMessage('assistant', data.answer || data.summary || 'No answer was returned.', data);
    if (data.mode === 'need_location') {
      pendingQuery = text;
      setStatus('Location needed');
    } else {
      setStatus(data.status === 'warning' ? 'Check conditions' : 'Ready');
    }
  } catch (error) {
    if (error.name === 'AbortError') {
      appendMessage('assistant', 'Response paused. You can send a new question.');
      setStatus('Paused');
    } else {
      appendMessage('assistant', `The request could not be completed: ${error.message}`);
      setStatus('Service unavailable', 'error');
    }
  } finally {
    thinking.remove();
    activeRequest = null;
    sendButton.disabled = false;
    sendButton.innerHTML = '<span>Send</span><span aria-hidden="true">↗</span>';
  }
}

form.addEventListener('submit', (event) => {
  event.preventDefault();
  if (activeRequest) {
    activeRequest.abort();
    return;
  }
  sendMessage(input.value);
});

input.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

document.querySelectorAll('[data-query]').forEach((button) => {
  button.addEventListener('click', () => sendMessage(button.dataset.query));
});

"""JavaScript widget generator and API key embed code."""

import json
from typing import Optional

from src.config import settings


WIDGET_JS_TEMPLATE = """
(function() {
  'use strict';

  var config = {CONFIG_JSON};
  var apiKey = '{API_KEY}';
  var apiEndpoint = '{API_ENDPOINT}';

  // Styles
  var styles = `
    #cbp-chat-container {
      position: fixed;
      {POSITION_CSS}
      z-index: 99999;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }
    #cbp-toggle-btn {
      width: 56px;
      height: 56px;
      border-radius: 50%;
      background: {primary_color};
      border: none;
      cursor: pointer;
      box-shadow: 0 4px 20px rgba(0,0,0,0.3);
      display: flex;
      align-items: center;
      justify-content: center;
      transition: transform 0.2s;
    }
    #cbp-toggle-btn:hover { transform: scale(1.1); }
    #cbp-chat-window {
      width: {width}px;
      height: {height}px;
      background: {background_color};
      border-radius: 16px;
      box-shadow: 0 8px 40px rgba(0,0,0,0.4);
      display: none;
      flex-direction: column;
      overflow: hidden;
      margin-bottom: 12px;
      border: 1px solid rgba(255,255,255,0.1);
    }
    #cbp-chat-window.open { display: flex; }
    #cbp-header {
      background: {primary_color};
      padding: 16px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    #cbp-header h3 { margin: 0; color: #fff; font-size: 16px; font-weight: 600; }
    #cbp-close-btn {
      background: none; border: none; color: #fff;
      cursor: pointer; font-size: 20px; padding: 0; line-height: 1;
    }
    #cbp-messages {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .cbp-msg { max-width: 85%; word-wrap: break-word; line-height: 1.5; }
    .cbp-msg-user {
      align-self: flex-end;
      background: {primary_color};
      color: #fff;
      padding: 10px 14px;
      border-radius: 18px 18px 4px 18px;
      font-size: 14px;
    }
    .cbp-msg-bot {
      align-self: flex-start;
      background: rgba(255,255,255,0.08);
      color: {text_color};
      padding: 10px 14px;
      border-radius: 18px 18px 18px 4px;
      font-size: 14px;
    }
    .cbp-sources {
      font-size: 11px;
      opacity: 0.6;
      margin-top: 6px;
      color: {text_color};
    }
    #cbp-suggestions {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      padding: 0 16px 8px;
    }
    .cbp-suggestion-btn {
      background: rgba(255,255,255,0.08);
      border: 1px solid rgba(255,255,255,0.15);
      color: {text_color};
      padding: 6px 12px;
      border-radius: 20px;
      cursor: pointer;
      font-size: 12px;
      transition: background 0.2s;
    }
    .cbp-suggestion-btn:hover { background: rgba(255,255,255,0.15); }
    #cbp-input-area {
      padding: 12px 16px;
      border-top: 1px solid rgba(255,255,255,0.08);
      display: flex;
      gap: 8px;
    }
    #cbp-input {
      flex: 1;
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.12);
      color: {text_color};
      padding: 10px 14px;
      border-radius: 24px;
      font-size: 14px;
      outline: none;
      transition: border-color 0.2s;
    }
    #cbp-input:focus { border-color: {primary_color}; }
    #cbp-send-btn {
      background: {primary_color};
      border: none;
      color: #fff;
      width: 40px;
      height: 40px;
      border-radius: 50%;
      cursor: pointer;
      font-size: 16px;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: opacity 0.2s;
      flex-shrink: 0;
    }
    #cbp-send-btn:hover { opacity: 0.85; }
    .cbp-typing { display: flex; gap: 4px; align-items: center; padding: 10px 14px; }
    .cbp-dot {
      width: 7px; height: 7px; border-radius: 50%;
      background: {text_color}; opacity: 0.5;
      animation: cbp-bounce 1.2s infinite ease-in-out;
    }
    .cbp-dot:nth-child(2) { animation-delay: 0.2s; }
    .cbp-dot:nth-child(3) { animation-delay: 0.4s; }
    @keyframes cbp-bounce {
      0%, 80%, 100% { transform: scale(0.7); }
      40% { transform: scale(1.0); }
    }
  `;

  var styleEl = document.createElement('style');
  styleEl.textContent = styles;
  document.head.appendChild(styleEl);

  // DOM
  var positionCSS = config.position === 'bottom-left'
    ? 'bottom: 24px; left: 24px;'
    : 'bottom: 24px; right: 24px;';

  var container = document.createElement('div');
  container.id = 'cbp-chat-container';

  var chatWindow = document.createElement('div');
  chatWindow.id = 'cbp-chat-window';
  chatWindow.innerHTML = `
    <div id="cbp-header">
      <h3>${config.bot_name}</h3>
      <button id="cbp-close-btn" aria-label="Close">&#x2715;</button>
    </div>
    <div id="cbp-messages"></div>
    <div id="cbp-suggestions"></div>
    <div id="cbp-input-area">
      <input id="cbp-input" type="text" placeholder="${config.placeholder_text}" autocomplete="off"/>
      <button id="cbp-send-btn" aria-label="Send">&#x2191;</button>
    </div>
  `;

  var toggleBtn = document.createElement('button');
  toggleBtn.id = 'cbp-toggle-btn';
  toggleBtn.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';

  container.appendChild(chatWindow);
  container.appendChild(toggleBtn);
  document.body.appendChild(container);

  var messages = document.getElementById('cbp-messages');
  var input = document.getElementById('cbp-input');
  var sendBtn = document.getElementById('cbp-send-btn');
  var suggestions = document.getElementById('cbp-suggestions');
  var conversationId = null;

  function addMsg(text, role, sources) {
    var div = document.createElement('div');
    div.className = 'cbp-msg cbp-msg-' + role;
    div.textContent = text;
    if (sources && sources.length && config.show_sources) {
      var src = document.createElement('div');
      src.className = 'cbp-sources';
      src.textContent = 'Sources: ' + sources.map(function(s){ return s.document_name; }).join(', ');
      div.appendChild(src);
    }
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    return div;
  }

  function addTyping() {
    var div = document.createElement('div');
    div.className = 'cbp-msg cbp-msg-bot';
    div.innerHTML = '<div class="cbp-typing"><div class="cbp-dot"></div><div class="cbp-dot"></div><div class="cbp-dot"></div></div>';
    div.id = 'cbp-typing';
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
  }

  function removeTyping() {
    var t = document.getElementById('cbp-typing');
    if (t) t.remove();
  }

  function showSuggestions() {
    suggestions.innerHTML = '';
    (config.suggested_questions || []).forEach(function(q) {
      var btn = document.createElement('button');
      btn.className = 'cbp-suggestion-btn';
      btn.textContent = q;
      btn.onclick = function() { sendMessage(q); };
      suggestions.appendChild(btn);
    });
  }

  async function sendMessage(text) {
    text = (text || input.value).trim();
    if (!text) return;
    input.value = '';
    suggestions.innerHTML = '';
    addMsg(text, 'user');
    addTyping();
    sendBtn.disabled = true;

    try {
      var resp = await fetch(apiEndpoint + '/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': apiKey
        },
        body: JSON.stringify({
          message: text,
          conversation_id: conversationId,
          stream: true,
          include_sources: config.show_sources
        })
      });

      removeTyping();
      var botDiv = addMsg('', 'bot');
      var reader = resp.body.getReader();
      var decoder = new TextDecoder();
      var fullContent = '';
      var lastSources = [];

      while (true) {
        var result = await reader.read();
        if (result.done) break;
        var lines = decoder.decode(result.value).split('\\n');
        for (var line of lines) {
          if (line.startsWith('data: ')) {
            try {
              var data = JSON.parse(line.slice(6));
              if (data.type === 'chunk') {
                fullContent += data.content;
                botDiv.firstChild ? (botDiv.firstChild.textContent = fullContent) : (botDiv.textContent = fullContent);
              } else if (data.type === 'sources') {
                lastSources = data.sources;
              } else if (data.type === 'done') {
                conversationId = data.conversation_id;
                if (lastSources.length && config.show_sources) {
                  var src = document.createElement('div');
                  src.className = 'cbp-sources';
                  src.textContent = 'Sources: ' + lastSources.map(function(s){ return s.document_name; }).join(', ');
                  botDiv.appendChild(src);
                }
              }
            } catch(e) {}
          }
        }
        messages.scrollTop = messages.scrollHeight;
      }
    } catch(e) {
      removeTyping();
      addMsg('Sorry, there was an error. Please try again.', 'bot');
    }
    sendBtn.disabled = false;
  }

  // Welcome message
  setTimeout(function() {
    addMsg(config.welcome_message, 'bot');
    showSuggestions();
  }, 300);

  toggleBtn.addEventListener('click', function() {
    chatWindow.classList.toggle('open');
  });
  document.getElementById('cbp-close-btn').addEventListener('click', function() {
    chatWindow.classList.remove('open');
  });
  sendBtn.addEventListener('click', function() { sendMessage(); });
  input.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') sendMessage();
  });
})();
"""


def generate_widget_js(
    api_key: str,
    project_id: str,
    widget_config: dict,
    api_base_url: Optional[str] = None,
) -> str:
    """Generate the embeddable JavaScript widget."""
    base_url = api_base_url or settings.api_base_url
    api_endpoint = f"{base_url}/api/v1/public/{project_id}"

    config_json = json.dumps(widget_config, ensure_ascii=False)

    position = widget_config.get("position", "bottom-right")
    if position == "bottom-left":
        position_css = "bottom: 24px; left: 24px;"
    else:
        position_css = "bottom: 24px; right: 24px;"

    js = WIDGET_JS_TEMPLATE
    js = js.replace("{CONFIG_JSON}", config_json)
    js = js.replace("'{API_KEY}'", f"'{api_key}'")
    js = js.replace("'{API_ENDPOINT}'", f"'{api_endpoint}'")
    js = js.replace("{POSITION_CSS}", position_css)

    for key, value in widget_config.items():
        js = js.replace(f"{{{key}}}", str(value))

    return js


def generate_script_tag(
    api_key: str,
    project_id: str,
    widget_config: dict,
    api_base_url: Optional[str] = None,
) -> str:
    """Generate the <script> tag for embedding."""
    base_url = api_base_url or settings.api_base_url
    params = json.dumps({
        "projectId": project_id,
        "apiKey": api_key,
        "config": widget_config,
    })
    return (
        f'<script src="{base_url}/api/v1/widget.js" '
        f'data-config=\'{params}\' async></script>'
    )


def generate_iframe_tag(
    api_key: str,
    project_id: str,
    widget_config: dict,
    api_base_url: Optional[str] = None,
) -> str:
    """Generate an iframe embed tag."""
    base_url = api_base_url or settings.api_base_url
    width = widget_config.get("width", 380)
    height = widget_config.get("height", 600)
    return (
        f'<iframe src="{base_url}/embed/{project_id}?key={api_key}" '
        f'width="{width}" height="{height}" frameborder="0" '
        f'style="border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,0.3);" '
        f'allow="microphone"></iframe>'
    )

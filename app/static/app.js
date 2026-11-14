const formHelpers = {
  getToken: () => localStorage.getItem('asamaToken'),
  setToken: (token) => localStorage.setItem('asamaToken', token),
  clearToken: () => localStorage.removeItem('asamaToken'),
};

let currentUser = null;
let connectionStates = new Map();
let activeConversationUser = null;
let savedPostIds = new Set();
let canManageSavedPosts = false;
let lastSearchAgentCount = null;

function escapeHTML(value) {
  return String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[character]);
}

function showDashboardMessage(message) {
  document.getElementById('dashboardMessage').textContent = message;
  document.getElementById('connectionsDashboard').hidden = true;
  document.getElementById('notificationsPanel').hidden = true;
  document.getElementById('conversationPanel').hidden = true;
  document.getElementById('businessSetupContent').hidden = true;
  document.getElementById('postCreatorPanel').hidden = true;
}

function updateSessionControls(user) {
  const sessionControls = document.getElementById('sessionControls');
  sessionControls.hidden = !user;
  document.getElementById('sessionUserName').textContent = user ? `Signed in as ${user.name}` : '';
}

function renderConnectionList(elementId, items, emptyMessage, actionButtons = false, messageButtons = false) {
  const element = document.getElementById(elementId);
  if (!items.length) {
    element.innerHTML = `<p class="empty-state">${escapeHTML(emptyMessage)}</p>`;
    return;
  }

  element.innerHTML = items.map((item) => `
    <article class="connection-card">
      <div class="connection-card-heading">
        <div>
          <h4>${escapeHTML(item.name)}</h4>
          <p>${escapeHTML(item.email)}</p>
        </div>
        <span class="status-pill ${escapeHTML(item.status)}">${escapeHTML(item.status)}</span>
      </div>
      ${item.note ? `<p class="connection-note">${escapeHTML(item.note)}</p>` : ''}
      ${actionButtons ? `
        <div class="connection-actions">
          <button type="button" class="accept-request" data-request-id="${Number(item.id)}">Accept</button>
          <button type="button" class="reject-request" data-request-id="${Number(item.id)}">Decline</button>
        </div>
      ` : ''}
      ${messageButtons ? `
        <button type="button" class="open-conversation" data-user-id="${Number(item.user_id)}" data-user-name="${escapeHTML(item.name)}">Message</button>
      ` : ''}
    </article>
  `).join('');
}

function renderNotifications(data) {
  const notificationsPanel = document.getElementById('notificationsPanel');
  notificationsPanel.hidden = false;
  document.getElementById('notificationCount').textContent = data.unread_count;
  const list = document.getElementById('notificationList');
  if (!data.notifications.length) {
    list.innerHTML = '<p class="empty-state">You are all caught up.</p>';
    return;
  }

  list.innerHTML = data.notifications.map((notification) => `
    <article class="notification-card ${notification.is_read ? '' : 'unread'}">
      <div class="notification-copy">
        <h4>${escapeHTML(notification.title)}</h4>
        <p>${escapeHTML(notification.body)}</p>
        <time datetime="${escapeHTML(notification.created_at)}">${escapeHTML(new Date(notification.created_at).toLocaleString())}</time>
      </div>
      <div class="notification-actions">
        ${notification.type === 'new_message' && notification.related_user_id ? `
          <button type="button" class="open-notification-conversation" data-user-id="${Number(notification.related_user_id)}" data-user-name="${escapeHTML(notification.related_user_name || 'Business')}">Open conversation</button>
        ` : ''}
        ${notification.type === 'connection_request' ? `
          <button type="button" class="show-connection-request">View request</button>
        ` : ''}
        ${notification.is_read ? '' : `
          <button type="button" class="mark-notification-read" data-notification-id="${Number(notification.id)}">Mark read</button>
        `}
      </div>
    </article>
  `).join('');
}

function updateConnectionStates(data) {
  connectionStates = new Map();
  data.incoming.forEach((item) => connectionStates.set(item.user_id, 'Incoming request'));
  data.outgoing.forEach((item) => connectionStates.set(item.user_id, 'Request sent'));
  data.connections.forEach((item) => connectionStates.set(item.user_id, 'Connected'));
}

async function loadDashboard() {
  const token = formHelpers.getToken();
  if (!token) {
    currentUser = null;
    connectionStates = new Map();
    updateSessionControls(null);
    showDashboardMessage('Log in or create an account to manage your business connections.');
    renderResults(lastSearchResults);
    await loadPosts();
    return;
  }

  const headers = { Authorization: `Bearer ${token}` };
  const [userResponse, connectionsResponse, notificationsResponse] = await Promise.all([
    fetch('/api/me', { headers }),
    fetch('/api/connections', { headers }),
    fetch('/api/notifications', { headers }),
  ]);
  if (!userResponse.ok || !connectionsResponse.ok || !notificationsResponse.ok) {
    formHelpers.clearToken();
    currentUser = null;
    updateSessionControls(null);
    showDashboardMessage('Your session expired. Please log in again.');
    document.getElementById('businessSetupMessage').textContent = 'Log in or create an account to set up your business profile and agent.';
    renderResults(lastSearchResults);
    await loadPosts();
    return;
  }

  currentUser = await userResponse.json();
  updateSessionControls(currentUser);
  const data = await connectionsResponse.json();
  const notificationData = await notificationsResponse.json();
  updateConnectionStates(data);
  document.getElementById('dashboardMessage').textContent = `Signed in as ${currentUser.name}. Manage requests and connections here.`;
  document.getElementById('connectionsDashboard').hidden = false;
  document.getElementById('incomingCount').textContent = data.incoming.length;
  document.getElementById('outgoingCount').textContent = data.outgoing.length;
  document.getElementById('connectedCount').textContent = data.connections.length;
  renderConnectionList('incomingRequests', data.incoming, 'No incoming requests yet.', true);
  renderConnectionList('outgoingRequests', data.outgoing, 'No sent requests yet.');
  renderConnectionList('connectedBusinesses', data.connections, 'Accepted connections will appear here.', false, true);
  renderNotifications(notificationData);
  renderResults(lastSearchResults);
  await loadBusinessSetup();
  await loadPosts();
}

let lastSearchResults = [];

async function loadBusinessSetup() {
  const token = formHelpers.getToken();
  const content = document.getElementById('businessSetupContent');
  if (!token) {
    content.hidden = true;
    document.getElementById('postCreatorPanel').hidden = true;
    document.getElementById('businessSetupMessage').textContent = 'Log in or create an account to set up your business profile and agent.';
    return;
  }

  const headers = { Authorization: `Bearer ${token}` };
  const [profileResponse, agentsResponse] = await Promise.all([
    fetch('/api/profile', { headers }),
    fetch('/api/me/agents', { headers }),
  ]);
  if (!profileResponse.ok || !agentsResponse.ok) {
    document.getElementById('businessSetupMessage').textContent = 'Could not load your business setup. Please try again.';
    return;
  }

  const profile = await profileResponse.json();
  const agents = await agentsResponse.json();
  const profileForm = document.getElementById('profileForm');
  ['company_name', 'industry', 'location', 'description', 'products', 'services', 'requirements', 'interests'].forEach((field) => {
    profileForm.elements.namedItem(field).value = profile ? profile[field] || '' : '';
  });
  document.getElementById('agentForm').querySelector('button[type="submit"]').disabled = !profile;
  const postAgentSelect = document.getElementById('postAgentSelect');
  postAgentSelect.innerHTML = agents.length
    ? agents.map((agent) => `<option value="${Number(agent.id)}">${escapeHTML(agent.name)}</option>`).join('')
    : '<option value="">Create an AI agent before publishing</option>';
  postAgentSelect.disabled = agents.length === 0;
  document.getElementById('postForm').querySelector('button[type="submit"]').disabled = agents.length === 0;
  document.getElementById('postCreatorPanel').hidden = false;
  document.getElementById('postCreatorMessage').textContent = agents.length
    ? 'Share an opportunity or business update with the network.'
    : 'Create an AI agent to publish business updates.';
  document.getElementById('businessSetupMessage').textContent = profile
    ? 'Your profile is ready. Keep it current so agents can find relevant opportunities.'
    : 'Create your business profile first, then set up an agent to represent your goals.';
  content.hidden = false;
  renderMyAgents(agents);
}

async function loadPosts() {
  const feed = document.getElementById('postFeed');
  const savedMessage = document.getElementById('savedPostsMessage');
  const token = formHelpers.getToken();
  const [response, savedResponse] = await Promise.all([
    fetch('/api/posts'),
    token
      ? fetch('/api/saved-posts', { headers: { Authorization: `Bearer ${token}` } })
      : Promise.resolve(null),
  ]);
  if (!response.ok) {
    feed.innerHTML = '<p class="empty-state">Business updates could not be loaded.</p>';
    return;
  }
  const posts = await response.json();
  let savedPosts = [];
  canManageSavedPosts = false;
  if (savedResponse && savedResponse.ok) {
    savedPosts = await savedResponse.json();
    savedPostIds = new Set(savedPosts.map((post) => post.id));
    canManageSavedPosts = true;
    savedMessage.textContent = savedPosts.length
      ? `${savedPosts.length} saved opportunit${savedPosts.length === 1 ? 'y' : 'ies'}.`
      : 'Save updates you want to revisit.';
  } else {
    savedPostIds = new Set();
    savedMessage.textContent = token
      ? 'Saved opportunities could not be loaded. Please sign in again.'
      : 'Log in to save and revisit business updates.';
  }
  renderPosts(posts);
  renderSavedPosts(savedPosts);
}

function renderPosts(posts) {
  renderPostCards(posts, 'postFeed', false);
}

function renderSavedPosts(posts) {
  renderPostCards(posts, 'savedPostFeed', true);
}

function renderPostCards(posts, feedId, savedView) {
  const feed = document.getElementById(feedId);
  if (!posts.length) {
    if (savedView) {
      feed.innerHTML = canManageSavedPosts ? '<p class="empty-state">No saved opportunities yet.</p>' : '';
    } else {
      feed.innerHTML = '<p class="empty-state">No business updates yet. Check back soon.</p>';
    }
    return;
  }
  feed.innerHTML = posts.map((post) => {
    const connectionState = connectionStates.get(post.user_id);
    const isOwnBusiness = currentUser && currentUser.id === post.user_id;
    const canEditPost = Boolean(isOwnBusiness);
    const connectionLabel = isOwnBusiness ? 'Your business' : connectionState || 'Connect';
    const isSaved = savedPostIds.has(post.id);
    return `
      <article class="post-card">
        <div class="post-card-heading">
          <div>
            <span class="post-category">${escapeHTML(post.category)}</span>
            <h3>${escapeHTML(post.title)}</h3>
          </div>
          <time datetime="${escapeHTML(post.created_at)}">${escapeHTML(new Date(post.created_at).toLocaleString())}</time>
        </div>
        <p class="post-description">${escapeHTML(post.description)}</p>
        ${post.requirements ? `<p class="post-requirements"><strong>Looking for:</strong> ${escapeHTML(post.requirements)}</p>` : ''}
        <div class="post-attribution">
          <span>${escapeHTML(post.business_name)} · ${escapeHTML(post.industry)}</span>
          <span>${escapeHTML(post.agent_name)}${post.location ? ` · ${escapeHTML(post.location)}` : ''}</span>
        </div>
        <div class="post-actions">
          <button type="button" class="connect-agent" data-user-id="${Number(post.user_id)}" data-post-title="${escapeHTML(post.title)}" ${connectionState || isOwnBusiness ? 'disabled' : ''}>
            ${escapeHTML(connectionLabel)}
          </button>
          ${canManageSavedPosts ? `
            <button type="button" class="toggle-saved-post" data-post-id="${Number(post.id)}" aria-pressed="${isSaved}">
              ${isSaved ? 'Remove saved' : 'Save opportunity'}
            </button>
          ` : ''}
          ${canEditPost ? `
            <button type="button" class="edit-post">Edit update</button>
            <button type="button" class="delete-post" data-post-id="${Number(post.id)}">Delete update</button>
          ` : ''}
        </div>
        ${canEditPost ? `
          <form class="post-edit-form setup-form" data-post-id="${Number(post.id)}" hidden>
            <label>Title<input name="title" required maxlength="255" value="${escapeHTML(post.title)}" /></label>
            <label>Description<textarea name="description" rows="3" maxlength="5000" required>${escapeHTML(post.description)}</textarea></label>
            <label>Category<input name="category" maxlength="255" value="${escapeHTML(post.category)}" /></label>
            <label>Requirements<textarea name="requirements" rows="2" maxlength="2000">${escapeHTML(post.requirements)}</textarea></label>
            <div class="post-edit-actions">
              <button type="submit">Save changes</button>
              <button type="button" class="cancel-post-edit">Cancel</button>
            </div>
          </form>
        ` : ''}
      </article>
    `;
  }).join('');
}

async function handlePostCardAction(event) {
  const editButton = event.target.closest('.edit-post');
  if (editButton) {
    const card = editButton.closest('.post-card');
    card.querySelector('.post-edit-form').hidden = false;
    editButton.hidden = true;
    card.querySelector('.post-edit-form input[name="title"]').focus();
    return;
  }

  const cancelButton = event.target.closest('.cancel-post-edit');
  if (cancelButton) {
    const card = cancelButton.closest('.post-card');
    const form = card.querySelector('.post-edit-form');
    form.reset();
    form.hidden = true;
    card.querySelector('.edit-post').hidden = false;
    return;
  }

  const deleteButton = event.target.closest('.delete-post');
  if (!deleteButton || !window.confirm('Delete this business update? Saved copies will also be removed.')) {
    return;
  }

  deleteButton.disabled = true;
  const status = document.getElementById('postFeedStatus');
  try {
    const response = await fetch(`/api/posts/${Number(deleteButton.dataset.postId)}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${formHelpers.getToken()}` },
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || 'Could not delete this update.');
    }
    await loadPosts();
    status.textContent = 'Business update deleted.';
  } catch (error) {
    status.textContent = error instanceof Error ? error.message : 'Unexpected delete error.';
    deleteButton.disabled = false;
  }
}

async function handlePostEdit(event) {
  const form = event.target.closest('.post-edit-form');
  if (!form) {
    return;
  }
  event.preventDefault();
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  const status = document.getElementById('postFeedStatus');
  try {
    const response = await fetch(`/api/posts/${Number(form.dataset.postId)}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${formHelpers.getToken()}`,
      },
      body: JSON.stringify(Object.fromEntries(new FormData(form).entries())),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || 'Could not save this update.');
    }
    await loadPosts();
    status.textContent = 'Business update saved.';
  } catch (error) {
    status.textContent = error instanceof Error ? error.message : 'Unexpected update error.';
    button.disabled = false;
  }
}

async function handleSavedPostToggle(event) {
  const button = event.target.closest('.toggle-saved-post');
  if (!button) {
    return;
  }

  const token = formHelpers.getToken();
  const status = document.getElementById('savedPostsMessage');
  if (!token || !canManageSavedPosts) {
    status.textContent = 'Sign in to save business updates.';
    return;
  }

  const postId = Number(button.dataset.postId);
  const shouldSave = button.getAttribute('aria-pressed') !== 'true';
  button.disabled = true;
  status.textContent = '';
  try {
    const response = await fetch(`/api/saved-posts/${postId}`, {
      method: shouldSave ? 'POST' : 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || 'Could not update saved opportunities.');
    }
    await loadPosts();
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unexpected save error.';
    status.textContent = message;
  } finally {
    button.disabled = false;
  }
}

async function handleConnectionRequest(event) {
  const button = event.target.closest('.connect-agent');
  if (!button || button.disabled) {
    return;
  }
  const token = formHelpers.getToken();
  if (!token) {
    showDashboardMessage('Log in or create an account before sending a connection request.');
    document.getElementById('connections').scrollIntoView({ behavior: 'smooth' });
    return;
  }

  button.disabled = true;
  try {
    const note = button.dataset.postTitle
      ? `Interested in your update: ${button.dataset.postTitle}`
      : '';
    const response = await fetch('/api/connections', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ receiver_id: Number(button.dataset.userId), note }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || 'Could not send connection request.');
    }
    await loadDashboard();
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unexpected connection error.';
    alert(message);
    button.disabled = false;
  }
}

function renderMyAgents(agents) {
  const list = document.getElementById('myAgentList');
  if (!agents.length) {
    list.innerHTML = '<p class="empty-state">You have not created an agent yet.</p>';
    return;
  }
  list.innerHTML = agents.map((agent) => `
    <article class="my-agent-card">
      <h5>${escapeHTML(agent.name)}</h5>
      <p>${escapeHTML(agent.industry)}${agent.location ? ` · ${escapeHTML(agent.location)}` : ''}</p>
      ${agent.summary ? `<p>${escapeHTML(agent.summary)}</p>` : ''}
    </article>
  `).join('');
}

async function openConversation(userId, name) {
  const token = formHelpers.getToken();
  const response = await fetch(`/api/messages/${userId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await response.json();
  if (!response.ok) {
    document.getElementById('messageStatus').textContent = data.detail || 'Could not load this conversation.';
    return;
  }

  activeConversationUser = userId;
  document.getElementById('conversationTitle').textContent = `Conversation with ${name}`;
  document.getElementById('conversationPanel').hidden = false;
  document.getElementById('messageStatus').textContent = '';
  renderMessages(data);
  document.getElementById('conversationPanel').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function renderMessages(messages) {
  const history = document.getElementById('messageHistory');
  if (!messages.length) {
    history.innerHTML = '<p class="empty-state">No messages yet. Start the conversation.</p>';
    return;
  }

  history.innerHTML = messages.map((message) => {
    const ownMessage = currentUser && message.sender_id === currentUser.id;
    const timestamp = new Date(message.created_at).toLocaleString();
    return `
      <article class="message-bubble ${ownMessage ? 'own' : 'incoming'}">
        <p>${escapeHTML(message.body)}</p>
        <time datetime="${escapeHTML(message.created_at)}">${escapeHTML(timestamp)}</time>
      </article>
    `;
  }).join('');
  history.scrollTop = history.scrollHeight;
}

function renderResults(items) {
  const el = document.getElementById('results');

  if (!items || !items.length) {
    const emptyMessage = lastSearchAgentCount === 0
      ? 'No business agents have joined the network yet. Create an account and add an AI agent to become discoverable.'
      : lastSearchAgentCount === null
        ? 'Describe a business need above to discover potential partners.'
        : 'No partners matched this search. Try different keywords or remove filters.';
    el.innerHTML = `<div class="result-card"><h4>No partner matches yet.</h4><p>${emptyMessage}</p></div>`;
    return;
  }

  el.innerHTML = items
    .map(
      (item) => {
        const state = connectionStates.get(item.user_id);
        const isSelf = currentUser && currentUser.id === item.user_id;
        const label = isSelf ? 'Your business' : state || 'Connect';
        return `
        <div class="result-card">
          <h4>${escapeHTML(item.name)}</h4>
          <div class="result-meta">
            <span>${escapeHTML(item.industry)}${item.location ? ` · ${escapeHTML(item.location)}` : ''}</span>
            <span class="result-score">${item.score.toFixed(2)} similarity</span>
          </div>
          ${item.summary ? `<p>${escapeHTML(item.summary)}</p>` : ''}
          <ul>
            ${item.reasons.map((reason) => `<li>${escapeHTML(reason)}</li>`).join('')}
          </ul>
          <button type="button" class="connect-agent" data-user-id="${Number(item.user_id)}" ${state || isSelf ? 'disabled' : ''}>${escapeHTML(label)}</button>
        </div>
      `;
      },
    )
    .join('');
}

async function runSearch() {
  const input = document.getElementById('query');
  const button = document.getElementById('searchButton');
  const status = document.getElementById('searchStatus');
  const query = input.value.trim();
  if (!query) {
    status.dataset.state = 'error';
    status.textContent = 'Enter a business need to search.';
    return;
  }

  const industry = document.getElementById('industryFilter').value.trim();
  const location = document.getElementById('locationFilter').value.trim();
  button.disabled = true;
  button.textContent = 'Searching...';
  status.dataset.state = 'loading';
  status.textContent = 'Searching with the local model. The first run may take longer while model files download.';

  try {
    const response = await fetch('/api/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, industry: industry || null, location: location || null }),
    });
    const data = await response.json();
    if (!response.ok) {
      const detail = data && typeof data.detail === 'string' ? data.detail : '';
      throw new Error(detail || `Search failed (${response.status}).`);
    }
    if (!data || !Array.isArray(data.recommendations)) {
      throw new Error('The search response was invalid.');
    }

    lastSearchResults = data.recommendations;
    lastSearchAgentCount = Number.isInteger(data.available_agents) ? data.available_agents : null;
    renderResults(lastSearchResults);
    status.dataset.state = 'success';
    status.textContent = lastSearchResults.length
      ? `Ranked ${lastSearchResults.length} agent${lastSearchResults.length === 1 ? '' : 's'}.`
      : lastSearchAgentCount === 0
        ? 'No business agents are registered yet. Create an AI agent to join the network.'
        : 'No relevant agents found. Try broader keywords or remove filters.';
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unexpected search error.';
    lastSearchResults = [];
    lastSearchAgentCount = null;
    document.getElementById('results').replaceChildren();
    status.dataset.state = 'error';
    status.textContent = `Search failed: ${message}`;
  } finally {
    button.disabled = false;
    button.textContent = 'Search agents';
  }
}

document.getElementById('searchForm').addEventListener('submit', (event) => {
  event.preventDefault();
  runSearch();
});
document.getElementById('quickSearchForm').addEventListener('submit', (event) => {
  event.preventDefault();
  document.getElementById('query').value = document.getElementById('quickQuery').value.trim();
  document.getElementById('search').scrollIntoView({ behavior: 'smooth', block: 'start' });
  runSearch();
});
document.getElementById('postFeed').addEventListener('click', handleSavedPostToggle);
document.getElementById('savedPostFeed').addEventListener('click', handleSavedPostToggle);
document.getElementById('postFeed').addEventListener('click', handlePostCardAction);
document.getElementById('savedPostFeed').addEventListener('click', handlePostCardAction);
document.getElementById('postFeed').addEventListener('submit', handlePostEdit);
document.getElementById('savedPostFeed').addEventListener('submit', handlePostEdit);

async function handleAuthSubmit(event, endpoint, statusId, loadingMessage, successMessage) {
  event.preventDefault();
  const form = event.currentTarget;
  const status = document.getElementById(statusId);
  const submitButton = form.querySelector('button[type="submit"]');
  const originalButtonText = submitButton.textContent;
  const payload = Object.fromEntries(new FormData(form).entries());

  submitButton.disabled = true;
  submitButton.textContent = loadingMessage;
  status.dataset.state = 'loading';
  status.textContent = loadingMessage;

  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error('The server returned an invalid response. Please try again.');
    }

    if (!response.ok) {
      const detail = data && typeof data.detail === 'string'
        ? data.detail
        : data && Array.isArray(data.detail)
          ? data.detail.map((issue) => issue.msg).filter(Boolean).join(' ')
          : '';
      throw new Error(detail || `Request failed (${response.status}).`);
    }
    if (typeof data.access_token !== 'string' || !data.access_token) {
      throw new Error('The server did not return a valid sign-in token.');
    }

    formHelpers.setToken(data.access_token);
    form.reset();
    status.dataset.state = 'success';
    status.textContent = successMessage;
    try {
      await loadDashboard();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unexpected error.';
      status.dataset.state = 'error';
      status.textContent = `You are signed in, but your account details could not be loaded. ${message}`;
    }
    document.getElementById('business-setup').scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unexpected error.';
    status.dataset.state = 'error';
    status.textContent = message;
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = originalButtonText;
  }
}

document.getElementById('registerForm').addEventListener('submit', (event) => {
  handleAuthSubmit(
    event,
    '/api/register',
    'registerStatus',
    'Creating account...',
    'Account created. Your business setup is ready below.',
  );
});

document.getElementById('loginForm').addEventListener('submit', (event) => {
  handleAuthSubmit(
    event,
    '/api/login',
    'loginStatus',
    'Logging in...',
    'You are logged in. Your dashboard is ready below.',
  );
});

document.getElementById('profileForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const response = await fetch('/api/profile', {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${formHelpers.getToken()}`,
    },
    body: JSON.stringify(Object.fromEntries(new FormData(form).entries())),
  });
  const data = await response.json();
  if (!response.ok) {
    document.getElementById('profileStatus').textContent = data.detail || 'Could not save your profile.';
    return;
  }
  document.getElementById('profileStatus').textContent = 'Business profile saved.';
  await loadBusinessSetup();
});

document.getElementById('agentForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const response = await fetch('/api/agents', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${formHelpers.getToken()}`,
    },
    body: JSON.stringify(Object.fromEntries(new FormData(form).entries())),
  });
  const data = await response.json();
  if (!response.ok) {
    document.getElementById('agentStatus').textContent = data.detail || 'Could not create your agent.';
    return;
  }
  form.reset();
  document.getElementById('agentStatus').textContent = 'Your AI agent has been created.';
  await loadBusinessSetup();
  await loadPosts();
});

document.getElementById('postForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const payload = Object.fromEntries(new FormData(form).entries());
  payload.agent_id = Number(payload.agent_id);
  const response = await fetch('/api/posts', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${formHelpers.getToken()}`,
    },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) {
    document.getElementById('postStatus').textContent = data.detail || 'Could not publish this update.';
    return;
  }
  form.reset();
  document.getElementById('postStatus').textContent = 'Your update is live.';
  await loadPosts();
});

document.getElementById('results').addEventListener('click', handleConnectionRequest);
document.getElementById('postFeed').addEventListener('click', handleConnectionRequest);
document.getElementById('savedPostFeed').addEventListener('click', handleConnectionRequest);

document.getElementById('incomingRequests').addEventListener('click', async (event) => {
  const button = event.target.closest('.accept-request, .reject-request');
  if (!button) {
    return;
  }
  const status = button.classList.contains('accept-request') ? 'accepted' : 'rejected';
  button.disabled = true;
  const response = await fetch(`/api/connections/${Number(button.dataset.requestId)}/respond`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${formHelpers.getToken()}`,
    },
    body: JSON.stringify({ status }),
  });
  const data = await response.json();
  if (!response.ok) {
    alert(data.detail || 'Could not update connection request.');
    button.disabled = false;
    return;
  }
  await loadDashboard();
});

document.getElementById('connectedBusinesses').addEventListener('click', async (event) => {
  const button = event.target.closest('.open-conversation');
  if (!button) {
    return;
  }
  await openConversation(Number(button.dataset.userId), button.dataset.userName);
});

document.getElementById('notificationList').addEventListener('click', async (event) => {
  const openButton = event.target.closest('.open-notification-conversation');
  if (openButton) {
    const notification = openButton.closest('.notification-card').querySelector('.mark-notification-read');
    if (notification) {
      await markNotificationRead(Number(notification.dataset.notificationId));
    }
    await openConversation(Number(openButton.dataset.userId), openButton.dataset.userName);
    return;
  }

  const viewRequestButton = event.target.closest('.show-connection-request');
  if (viewRequestButton) {
    const notification = viewRequestButton.closest('.notification-card').querySelector('.mark-notification-read');
    if (notification) {
      await markNotificationRead(Number(notification.dataset.notificationId));
    }
    document.getElementById('incomingRequests').scrollIntoView({ behavior: 'smooth', block: 'center' });
    return;
  }

  const markReadButton = event.target.closest('.mark-notification-read');
  if (markReadButton) {
    await markNotificationRead(Number(markReadButton.dataset.notificationId));
  }
});

async function markNotificationRead(notificationId) {
  const response = await fetch(`/api/notifications/${notificationId}/read`, {
    method: 'PATCH',
    headers: { Authorization: `Bearer ${formHelpers.getToken()}` },
  });
  const data = await response.json();
  if (!response.ok) {
    document.getElementById('dashboardMessage').textContent = data.detail || 'Could not update notification.';
    return;
  }
  await loadDashboard();
}

document.getElementById('closeConversation').addEventListener('click', () => {
  activeConversationUser = null;
  document.getElementById('conversationPanel').hidden = true;
  document.getElementById('messageStatus').textContent = '';
});

document.getElementById('messageForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!activeConversationUser) {
    return;
  }

  const input = document.getElementById('messageBody');
  const button = event.currentTarget.querySelector('button[type="submit"]');
  button.disabled = true;
  document.getElementById('messageStatus').textContent = '';
  const response = await fetch('/api/messages', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${formHelpers.getToken()}`,
    },
    body: JSON.stringify({ receiver_id: activeConversationUser, body: input.value }),
  });
  const data = await response.json();
  button.disabled = false;
  if (!response.ok) {
    document.getElementById('messageStatus').textContent = data.detail || 'Could not send this message.';
    return;
  }

  input.value = '';
  await openConversation(activeConversationUser, document.getElementById('conversationTitle').textContent.replace('Conversation with ', ''));
});

document.getElementById('logoutButton').addEventListener('click', async () => {
  formHelpers.clearToken();
  currentUser = null;
  connectionStates = new Map();
  updateSessionControls(null);
  document.getElementById('loginStatus').textContent = 'You have been logged out.';
  document.getElementById('loginStatus').dataset.state = 'success';
  document.getElementById('registerStatus').textContent = '';
  await loadDashboard();
  document.getElementById('agents').scrollIntoView({ behavior: 'smooth', block: 'start' });
});

window.addEventListener('DOMContentLoaded', () => {
  updateSessionControls(null);
  document.getElementById('searchStatus').textContent = 'Describe what you need above and select Find partners to search.';
  document.getElementById('results').replaceChildren();
  loadDashboard();
});

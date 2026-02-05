/**
 * Inline table cell editing: click a cell to edit, blur or Enter to PATCH.
 * Requires data-editable, data-entity, data-id, data-field on each editable <td>.
 * Optional: data-detail-url (restore as link), data-type="select" with data-choices (JSON array of [value, label]).
 */
(function() {
  'use strict';

  var CHOICES = {
    outreach_status: [
      ['', '—'],
      ['not_contacted', 'Not contacted'],
      ['reached_out', 'Reached out'],
      ['responded', 'Responded'],
      ['bounced', 'Bounced'],
      ['not_a_fit', 'Not a fit']
    ],
    priority_tier: [
      ['', '—'],
      [1, 'Tier 1'],
      [2, 'Tier 2'],
      [3, 'Tier 3']
    ]
  };

  function getCsrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
  }

  function getApiBase() {
    var base = document.querySelector('meta[name="api-base"]');
    return (base ? base.getAttribute('content') : '') || '';
  }

  function buildInput(cell) {
    var field = cell.getAttribute('data-field');
    var value = (cell.getAttribute('data-value') || '').replace(/^—$/, '');
    var type = cell.getAttribute('data-type') || 'text';
    var input;

    if (type === 'select') {
      var choices = CHOICES[field];
      if (!choices) {
        var dataChoices = cell.getAttribute('data-choices');
        try { choices = dataChoices ? JSON.parse(dataChoices) : []; } catch (e) { choices = []; }
      }
      input = document.createElement('select');
      input.className = 'form-control form-control-sm';
      (choices || []).forEach(function(opt) {
        var val = opt[0], label = opt[1];
        var option = document.createElement('option');
        option.value = val === null || val === undefined ? '' : String(val);
        option.textContent = label;
        if (String(value) === option.value) option.selected = true;
        input.appendChild(option);
      });
    } else {
      input = document.createElement('input');
      input.type = type === 'number' ? 'number' : (type === 'url' ? 'url' : 'text');
      input.className = 'form-control form-control-sm';
      input.value = value;
      if (type === 'number') input.min = 0;
    }
    return input;
  }

  function displayValue(cell, value, field, detailUrl) {
    var type = cell.getAttribute('data-type') || 'text';
    var display = value === '' || value === null || value === undefined ? '—' : String(value);
    if (type === 'select') {
      var choices = CHOICES[field];
      if (choices) {
        var opt = choices.find(function(o) { return String(o[0]) === String(value); });
        if (opt) display = opt[1];
      }
    }
    if (field === 'priority_tier' && value !== '' && value !== null && value !== undefined) {
      display = 'Tier ' + value;
    }
    if (detailUrl && (field === 'name' || field === 'first_name')) {
      var a = document.createElement('a');
      a.href = detailUrl;
      a.className = 'text-decoration-none' + (field === 'name' ? ' fw-semibold' : '');
      a.textContent = display || '—';
      return a;
    }
    if (field === 'linkedin_url' || field === 'linkedin') {
      if (!display || display === '—') return document.createTextNode('—');
      var link = document.createElement('a');
      link.href = display;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.title = display;
      link.innerHTML = '<i class="fab fa-linkedin"></i>';
      return link;
    }
    if (field === 'email' && display !== '—') {
      var mailto = document.createElement('a');
      mailto.href = 'mailto:' + display;
      mailto.textContent = display;
      return mailto;
    }
    return document.createTextNode(display);
  }

  function showError(cell, message) {
    var existing = cell.querySelector('.inline-edit-error');
    if (existing) existing.remove();
    var err = document.createElement('div');
    err.className = 'inline-edit-error small text-danger mt-1';
    err.textContent = message;
    cell.appendChild(err);
    setTimeout(function() { err.remove(); }, 4000);
  }

  function startEdit(cell) {
    if (cell.getAttribute('data-editing') === '1') return;
    cell.setAttribute('data-editing', '1');
    var savedHtml = cell.innerHTML;
    cell.setAttribute('data-saved-html', savedHtml);
    var value = cell.getAttribute('data-value');
    if (value === null) {
      var text = cell.textContent.trim();
      cell.setAttribute('data-value', text === '—' ? '' : text);
    }
    cell.innerHTML = '';
    var input = buildInput(cell);
    cell.appendChild(input);
    input.focus();

    function finish(cancel) {
      cell.removeAttribute('data-editing');
      if (cancel) {
        cell.innerHTML = cell.getAttribute('data-saved-html') || savedHtml;
        return;
      }
      var newVal = input.type === 'select-one' ? input.value : input.value.trim();
      var entity = cell.getAttribute('data-entity');
      var id = cell.getAttribute('data-id');
      var field = cell.getAttribute('data-field');
      var detailUrl = cell.getAttribute('data-detail-url') || '';
      var apiBase = getApiBase();
      var path = entity === 'company' ? 'companies' : 'contacts';
      var url = apiBase + '/api/' + path + '/' + id + '/';

      var payload = {};
      var type = cell.getAttribute('data-type') || 'text';
      if (type === 'number' || field === 'priority_tier') {
        payload[field] = newVal === '' ? null : parseInt(newVal, 10);
      } else {
        payload[field] = newVal === '' ? '' : newVal;
      }

      var csrf = getCsrfToken();
      var headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      };
      if (csrf) headers['X-CSRFToken'] = csrf;

      fetch(url, {
        method: 'PATCH',
        headers: headers,
        body: JSON.stringify(payload),
        credentials: 'same-origin'
      }).then(function(res) {
        if (res.ok) {
          cell.setAttribute('data-value', newVal);
          cell.innerHTML = '';
          var displayNode = displayValue(cell, newVal, field, detailUrl);
          if (displayNode.nodeType === Node.TEXT_NODE) cell.appendChild(displayNode);
          else cell.appendChild(displayNode);
        } else {
          return res.json().then(function(data) {
            var msg = (data[field] && data[field].join) ? data[field].join(' ') : (data.detail || 'Save failed');
            showError(cell, msg);
            cell.innerHTML = savedHtml;
            cell.removeAttribute('data-saved-html');
          }).catch(function() {
            showError(cell, 'Save failed');
            cell.innerHTML = savedHtml;
          });
        }
      }).catch(function() {
        showError(cell, 'Network error');
        cell.innerHTML = savedHtml;
      });
    }

    input.addEventListener('blur', function() { setTimeout(function() { finish(false); }, 150); });
    input.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') { e.preventDefault(); finish(false); }
      if (e.key === 'Escape') { e.preventDefault(); finish(true); }
    });
  }

  function init() {
    document.querySelectorAll('[data-editable]').forEach(function(cell) {
      var value = cell.textContent.trim();
      if (value !== '—' && !cell.hasAttribute('data-value')) {
        if (cell.querySelector('a[href^="mailto:"]')) value = cell.querySelector('a').textContent.trim();
        else if (cell.querySelector('a[href]')) value = cell.querySelector('a').textContent.trim();
        else if (cell.querySelector('a[href*="linkedin"]')) value = cell.querySelector('a').href || '';
        cell.setAttribute('data-value', value);
      }
      cell.addEventListener('click', function(e) {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'A') return;
        e.preventDefault();
        startEdit(cell);
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

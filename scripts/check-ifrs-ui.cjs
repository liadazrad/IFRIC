const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');

class Element {
  constructor(tagName = 'div') {
    this.tagName = tagName.toUpperCase();
    this.children = [];
    this.events = {};
    this.dataset = {};
    this.value = '';
    this.classList = { toggle() {} };
  }
  set innerHTML(_value) { this.children = []; }
  addEventListener(name, handler) { this.events[name] = handler; }
  appendChild(child) {
    this.children.push(child);
    if (this.tagName === 'SELECT' && this.children.length === 1) this.value = child.value;
    return child;
  }
  append(...children) { this.children.push(...children); }
  setAttribute() {}
  removeAttribute() {}
  focus() { this.focused = true; }
  scrollIntoView() { this.scrolledIntoView = true; }
  get options() { return this.children; }
  showModal() { this.open = true; }
}

const ids = new Map([...html.matchAll(/<(\w+)\b[^>]*\bid="([\w-]+)"/g)]
  .map(([, tag, id]) => [id, new Element(tag)]));
const tab = (key, value) => Object.assign(new Element(), { dataset: { [key]: value } });
const tabs = [...html.matchAll(/data-tab="([\w-]+)"/g)].map(([, id]) => tab('tab', id));
const panels = [...html.matchAll(/data-tab-panel="([\w-]+)"/g)].map(([, id]) => tab('tabPanel', id));
const shortcuts = [...html.matchAll(/data-open-tab="([\w-]+)"/g)].map(([, id]) => tab('openTab', id));
const document = {
  getElementById: (id) => ids.get(id),
  createElement: (tag) => new Element(tag),
  querySelectorAll: (selector) => ({
    '.tab-button': tabs, '.tab-panel': panels, '[data-open-tab]': shortcuts
  })[selector] || []
};

const context = vm.createContext({
  document, URL, Intl, console, HTMLElement: Element,
  window: { location: new URL('http://local.test/') },
  localStorage: { getItem: () => null, setItem: () => {} },
  fetch: async (url) => ({ ok: true, json: () => JSON.parse(fs.readFileSync(path.join(root, new URL(url).pathname), 'utf8')) })
});

const script = fs.readFileSync(path.join(root, 'app.js'), 'utf8');
const initialized = script.slice(0, script.lastIndexOf('initialize().catch')) + 'initialize();';

(async () => {
  await vm.runInContext(initialized, context);
  assert.equal(tabs.length, 3);
  assert.ok(ids.get('home-highlights').children.length > 0);
  assert.equal(ids.get('home-pending').children.length, 6);
  const changes = ids.get('home-updates');
  const shortFeed = changes.children.length;
  if (!ids.get('home-more-updates').hidden) {
    ids.get('home-more-updates').events.click();
    assert.ok(changes.children.length > shortFeed);
  }
  const home = ids.get('global-search');
  const homeStandard = ids.get('home-standard');
  homeStandard.value = 'IFRS 18';
  homeStandard.events.change();
  const archive = JSON.parse(fs.readFileSync(path.join(root, 'data/ifric.json'), 'utf8'));
  const expectedDecisions = archive.filter((item) => (item.standards || [item.standard]).includes('IFRS 18'));
  assert.ok(expectedDecisions.length > 0);
  assert.equal(ids.get('home-pending').children.length, expectedDecisions.length);
  assert.ok(ids.get('home-highlights').children.every((row) =>
    row.children[0].children.some((entry) => entry.textContent.includes('IFRS 18'))));
  const snapshot = JSON.parse(fs.readFileSync(path.join(root, 'data/ifrs-monitor.json'), 'utf8'));
  const entries = new Map([...snapshot.scheduled, ...snapshot.active, ...archive].map((item) => [item.id, item]));
  const expectedUpdates = snapshot.changes.filter((entry) => entries.get(entry.itemId)?.standards?.includes('IFRS 18'));
  assert.equal(ids.get('home-activity').hidden, expectedUpdates.length === 0);
  if (expectedUpdates.length) {
    assert.equal(changes.children.length, shortFeed < snapshot.changes.length ? expectedUpdates.length : Math.min(3, expectedUpdates.length));
  }
  home.value = 'Reassessment of Control';
  home.events.input();
  assert.equal(ids.get('home-pending').children[0].className, 'empty-state');
  homeStandard.value = 'IFRS 10';
  homeStandard.events.change();
  assert.ok(ids.get('home-pending').children.some((card) => card.children.some((child) => child.textContent?.includes('Reassessment of Control'))));
  shortcuts.find((entry) => entry.dataset.openTab === 'finals').events.click();
  assert.equal(ids.get('finals-standard').value, 'IFRS 10');
  tabs.find((entry) => entry.dataset.tab === 'home').events.click();
  ids.get('home-clear').events.click();
  assert.equal(home.value, '');
  assert.equal(homeStandard.value, 'all');
  assert.equal(ids.get('home-pending').children.length, 6);

  tabs.find((entry) => entry.dataset.tab === 'topics').events.click();
  const group = ids.get('topics-group');
  group.value = 'IASB';
  group.events.change();
  const projects = ids.get('topics-grid').children;
  assert.ok(projects.length > 1);
  assert.ok(projects.every((card) => card.children[0].children[0].textContent === 'IASB'));
  const topicStandard = ids.get('topics-standard');
  topicStandard.value = 'IFRS 18';
  topicStandard.events.change();
  assert.ok(ids.get('topics-grid').children.every((row) => row.className === 'empty-state' ||
    row.children[0].children.some((entry) => entry.textContent.includes('IFRS 18'))));

  tabs.find((entry) => entry.dataset.tab === 'finals').events.click();
  const filter = ids.get('finals-standard');
  filter.value = 'IFRS 10';
  filter.events.change();
  assert.ok(ids.get('finals-grid').children.length > 1);
  const decision = ids.get('finals-grid').children[0];
  decision.children.at(-1).children[0].events.click();
  assert.ok(ids.get('item-modal').open);
  assert.ok(ids.get('modal-links').children.some((link) => link.textContent.includes('סופית')));

  filter.value = 'IAS 27';
  filter.events.change();
  const archiveSearch = ids.get('finals-search');
  archiveSearch.value = 'AP4B: Step Acquisition';
  archiveSearch.events.input();
  const [stepAcquisition] = ids.get('finals-grid').children;
  assert.equal(ids.get('finals-grid').children.length, 1);
  const paperButton = stepAcquisition.children.at(-1).children.find((child) => child.textContent.startsWith('ניירות עבודה'));
  assert.ok(paperButton);
  paperButton.events.click();
  const paperHeading = ids.get('modal-related-heading');
  assert.equal(paperHeading.textContent, 'ניירות עבודה שקדמו להחלטה');
  assert.ok(paperHeading.focused && paperHeading.scrolledIntoView);
  const linkedPapers = ids.get('modal-related').children;
  assert.ok(linkedPapers.some((paper) => paper.children.at(-1).children.some((link) => link.href.endsWith('ap4b-ias-27-step-acquisition.pdf'))));
  assert.ok(linkedPapers.every((paper) => paper.children.at(-1).children.some((link) => link.textContent === 'דף הפגישה')));

  const unlinked = archive.find((item) => !item.relatedPapers?.length);
  if (unlinked) {
    vm.runInContext(`openItemModal(itemsById.get(${JSON.stringify(unlinked.id)}))`, context);
    assert.match(ids.get('modal-related').children[0].textContent, /טרם נמצא קישור מאומת/);
  }
  console.log('UI logic passed: search, filters, official decisions and preceding papers.');
})().catch((error) => { console.error(error); process.exitCode = 1; });

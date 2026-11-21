const statusLabel = document.getElementById("status-label");
const statusCount = document.getElementById("status-count");
const statusValue = document.getElementById("status-value");
const statusNote = document.getElementById("status-note");
const tabButtons = [...document.querySelectorAll(".tab-button")];
const tabPanels = [...document.querySelectorAll(".tab-panel")];
const globalSearch = document.getElementById("global-search");
const homeStandard = document.getElementById("home-standard");
const homeClear = document.getElementById("home-clear");
const homeLayout = document.getElementById("home-layout");
const homeActivity = document.getElementById("home-activity");
const homeFinalTitle = document.getElementById("home-final-title");
const pageTitle = document.getElementById("page-title");
const pageDescription = document.getElementById("page-description");
const homeSummary = document.getElementById("home-summary");
const homeHighlights = document.getElementById("home-highlights");
const homePending = document.getElementById("home-pending");
const homePendingSummary = document.getElementById("home-pending-summary");
const homeUpdates = document.getElementById("home-updates");
const homeUpdatesSummary = document.getElementById("home-updates-summary");
const homeMoreUpdates = document.getElementById("home-more-updates");
const homeLatestTitle = document.getElementById("home-latest-title");

const modal = document.getElementById("item-modal");
const modalMeta = document.getElementById("modal-meta");
const modalTitle = document.getElementById("modal-title");
const modalSubtitle = document.getElementById("modal-subtitle");
const modalSummary = document.getElementById("modal-summary");
const modalProposal = document.getElementById("modal-proposal");
const modalProposalSection = document.getElementById("modal-proposal-section");
const modalStaffSection = document.getElementById("modal-staff-section");
const modalStaffView = document.getElementById("modal-staff-view");
const modalCommitteeSection = document.getElementById("modal-committee-section");
const modalCommitteeView = document.getElementById("modal-committee-view");
const modalLinks = document.getElementById("modal-links");
const modalRelated = document.getElementById("modal-related");
const modalRelatedHeading = document.getElementById("modal-related-heading");
const modalReviewed = document.getElementById("modal-reviewed");

const controls = {
  finals: {
    search: document.getElementById("finals-search"),
    standard: document.getElementById("finals-standard"),
    summary: document.getElementById("finals-summary"),
    grid: document.getElementById("finals-grid"),
    clear: document.getElementById("finals-clear")
  },
  topics: {
    search: document.getElementById("topics-search"),
    standard: document.getElementById("topics-standard"),
    status: document.getElementById("topics-status"),
    group: document.getElementById("topics-group"),
    summary: document.getElementById("topics-summary"),
    meetings: document.getElementById("topics-meetings"),
    meetingSummary: document.getElementById("topics-meeting-summary"),
    projectSummary: document.getElementById("topics-project-summary"),
    grid: document.getElementById("topics-grid"),
    clear: document.getElementById("topics-clear")
  }
};

let activeTab = "home";
let ifricDecisions = [];
let monitor = { scheduled: [], active: [], changes: [] };
let itemsById = new Map();
let showAllUpdates = false;
let reviewedIds = loadReviewedIds();

const topicHeuristics = [
  [/hypothetical income and expenses/i, "הצגת הכנסות והוצאות היפותטיות במסגרת מדדי ביצוע שההנהלה מגדירה."],
  [/public communications/i, "בחינת השימוש במדדי ביצוע שההנהלה מגדירה בפרסומים חיצוניים לציבור."],
  [/single-investor fund|control assessment/i, "בחינת שליטה בקרן בעלת משקיע יחיד והאם יש לאחד את הקרן."],
  [/reassessment of control/i, "שאלה מתי יש להעריך מחדש שליטה לפי IFRS 10 לאחר שינוי בנסיבות."],
  [/foreign exchange difference/i, "סיווג הפרשי שער על פריט מוניטרי תוך־קבוצתי לפי מבנה IFRS 18."],
  [/battery under an offtake arrangement/i, "האם הטבות משימוש בסוללה תחת הסכם offtake יוצרות טיפול חשבונאי מסוים לפי IFRS 16."],
  [/fair presentation/i, "מתי סטייה מהצגה רגילה נדרשת כדי להשיג הצגה נאותה וציות מלא ל־IFRS."],
  [/disclose expenses by nature/i, "היקף הדרישה להציג הוצאות לפי מהות במסגרת IFRS 18."],
  [/derivative managing a foreign currency exposure/i, "סיווג רווחים והפסדים על נגזר שמנהל חשיפת מטבע חוץ."],
  [/specified main business activity/i, "סיווג פריטים בדוח רווח והפסד עבור ישות עם פעילות עסקית עיקרית מוגדרת."],
  [/taxes or other charges/i, "הצגת מסים או חיובים אחרים שאינם מסי הכנסה בדוח רווח והפסד."],
  [/embedded prepayment option/i, "האם אופציית פירעון מוקדם מוטמעת דורשת הפרדה מהמכשיר המארח."],
  [/transaction costs/i, "מה נחשב עלויות עסקה ואיך לטפל בהן לפני התקשרות סופית במכשיר פיננסי."],
  [/tuition fees/i, "מתי מוסד לימודי מכיר בהכנסות משכר לימוד לאורך תקופת השירות."],
  [/climate-related expenditure/i, "האם הוצאות אקלים ופעילויות פיתוח עומדות בהכרה כנכס בלתי מוחשי."]
];

const finalDecisionHeMap = {
  "Embedded Prepayment Option (IFRS 9)": {
    title: "אופציית פירעון מוקדם מובנית (IFRS 9)",
    summary: "הוועדה בחנה אם יש להפריד אופציית פירעון מוקדם מובנית בהתחייבות פיננסית וקבעה שהנושא אינו נפוץ דיו לתיקנון.",
    committee: "עמדת הוועדה היא שהפרקטיקה הקיימת אינה מצביעה על פיזור מהותי, ולכן לא נדרש פרויקט תקינה."
  },
  "Determining and Accounting for Transaction Costs (IFRS 9)": {
    title: "קביעת עלויות עסקה והטיפול בהן (IFRS 9)",
    summary: "הוועדה דנה בשאלה אילו עלויות טרום־חתימה יכולות להיחשב עלויות עסקה לפי IFRS 9.",
    committee: "עמדת הוועדה היא שהשונות בפרקטיקה אינה רחבה או מהותית ולכן לא הוסף פרויקט לתכנית העבודה."
  },
  "Recognition of Revenue from Tuition Fees (IFRS 15)": {
    title: "הכרה בהכנסות משכר לימוד (IFRS 15)",
    summary: "הוועדה בחנה על פני איזו תקופה יש להכיר בהכנסות משכר לימוד במוסדות חינוך.",
    committee: "הוועדה סברה שהשונות נובעת מהבדלים בנסיבות ולא ממחלוקת פרשנית רחבה."
  },
  "Recognition of Intangible Assets from Climate-related Expenditure (IAS 38)": {
    title: "הכרה בנכסים בלתי מוחשיים מהוצאות אקלים (IAS 38)",
    summary: "הוועדה בחנה אם השקעות בפעילויות מחקר ופיתוח סביב יעדי אקלים עומדות בתנאי ההכרה כנכס בלתי מוחשי.",
    committee: "עמדת הוועדה היא שאין פיזור מהותי בפרקטיקה ולכן אין צורך בפרויקט תקינה חדש."
  }
};

const stageLabels = {
  scheduled: "בסדר היום", discussed: "נדון לאחרונה", active: "פרויקט פעיל",
  consultation: "פתוח לתגובות", tentative: "החלטה מוצעת", "pending-board": "לפני פרסום החלטה",
  announced: "הוכרז על ידי IASB"
};
const milestones = {
  "Decide Project Direction": "קביעת כיוון הפרויקט",
  "Tentative Agenda Decision Feedback": "דיון בתגובות להחלטה מוצעת",
  "Agenda Decision": "פרסום החלטת סדר יום",
  "Exposure Draft": "פרסום טיוטת תקן", "Exposure Draft Feedback": "דיון בתגובות לטיוטה",
  "Request for Information Feedback": "בחינת תגובות לבקשת מידע",
  "Project Summary and Feedback Statement": "סיכום הפרויקט ופרסום משוב",
  "Proposed IFRS Taxonomy Update Feedback": "בחינת תגובות לעדכון הטקסונומיה",
  "Final Amendments": "פרסום תיקונים סופיים", "Final IFRS Taxonomy Update": "פרסום עדכון טקסונומיה סופי"
};
const paperKind = {
  comment_letter_analysis: "ניתוח תגובות", updated_wording: "נוסח מעודכן",
  initial_consideration: "בחינה ראשונית", staff_paper: "נייר צוות",
  tentative_agenda_decision: "החלטה מוצעת", iasb_follow_up: "דיון המשך"
};
const changeLabels = { new: "נושא נוסף למעקב", paper: "נייר עבודה פורסם", updated: "פריט עודכן", final: "החלטה סופית פורסמה" };
const pageCopy = {
  home: ["מעקב אחר החלטות ודיוני IFRS", "סדרי יום, עבודת התקינה והחלטות הוועדה, עם תקצירים בעברית."],
  topics: ["על הפרק", "סדרי יום ופרויקטים פעילים של IFRIC ו־IASB."],
  finals: ["החלטות סדר יום סופיות", "ארכיון החלטות IFRIC עם חיפוש בטקסט המלא וקישורים לניירות עבודה."]
};

function localToday() {
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Jerusalem" }).format(new Date());
}

function asDiscussion(item) {
  const stage = item.stage === "consultation" && item.commentDate < localToday() ? "feedback" : item.stage;
  return { ...item, stage, status: stageLabels[stage] || "בבחינת תגובות" };
}

function normalize(value) {
  return String(value || "").toLowerCase().replace(/\s+/g, " ").trim();
}

function loadReviewedIds() {
  try {
    const value = JSON.parse(localStorage.getItem("ifric-reviewed-items") || "[]");
    return new Set(Array.isArray(value) ? value : []);
  } catch {
    return new Set();
  }
}

function persistReviewedIds() {
  localStorage.setItem("ifric-reviewed-items", JSON.stringify([...reviewedIds]));
}

function formatDate(dateValue) {
  if (!dateValue) return "ללא תאריך";

  return new Intl.DateTimeFormat("he-IL", {
    year: "numeric",
    month: "long",
    day: "numeric"
  }).format(new Date(dateValue));
}

function decisionDate(item) {
  return item.datePrecision === "month"
    ? new Intl.DateTimeFormat("he-IL", { month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(item.publishedAt))
    : formatDate(item.publishedAt);
}

function getStandardSortKey(standard) {
  const match = String(standard || "").match(/\b(IAS|IFRS)\s+(\d+)\b/i);
  if (!match) {
    return { group: 99, number: Number.MAX_SAFE_INTEGER, label: standard || "" };
  }

  return {
    group: match[1].toUpperCase() === "IAS" ? 0 : 1,
    number: Number(match[2]),
    label: standard
  };
}

function sortStandards(values) {
  return [...values].sort((leftValue, rightValue) => {
    const left = getStandardSortKey(leftValue);
    const right = getStandardSortKey(rightValue);
    if (left.group !== right.group) return left.group - right.group;
    if (left.number !== right.number) return left.number - right.number;
    return left.label.localeCompare(right.label, "en");
  });
}

function getStatusTone(status) {
  if (/סופית/.test(status)) return "final";
  if (/מוצעת/.test(status)) return "tentative";
  if (/פתוח|ראשונית|בסדר היום/.test(status)) return "open";
  if (/עודכן|בטיפול/.test(status)) return "progress";
  if (/בדיקה/.test(status)) return "review";
  return "neutral";
}

function getDocumentTone(type) {
  if (/final/i.test(type)) return "final";
  if (/tentative|comment/i.test(type)) return "tentative";
  if (/initial|ongoing/i.test(type)) return "open";
  return "neutral";
}

function getHebrewTopicTitle(item) {
  return item.topicTitleHe || finalDecisionHeMap[item.title]?.title || item.topicTitleEn || item.title;
}

function getHebrewSummary(item) {
  if (item.summaryHe) return item.summaryHe;
  if (finalDecisionHeMap[item.title]?.summary) return finalDecisionHeMap[item.title].summary;

  const text = item.topicTitleEn || item.title || "";
  for (const [pattern, summary] of topicHeuristics) {
    if (pattern.test(text)) {
      return summary;
    }
  }

  if (item.topicTitleHe && item.finalAgendaDecisionUrl) return `נושא ההחלטה: ${item.topicTitleHe}.`;
  return item.paperPending ? "נייר העבודה יתווסף לאחר פרסומו." : "פרטי הדיון זמינים במקור הרשמי.";
}

function getCommitteeView(item) {
  return item.committeeViewHe || finalDecisionHeMap[item.title]?.committee || "";
}

function trackerSearchBlob(item) {
  return normalize([
    item.standard,
    ...(item.standards || []),
    item.topicTitleEn,
    item.topicTitleHe,
    item.summaryHe,
    item.staffViewHe,
    item.committeeViewHe,
    item.documentTitle,
    item.documentType,
    item.status,
    item.apNumber,
    item.group,
    item.nextMilestone,
    item.changeNoteHe,
    ...(item.relatedPapers || []).map((paper) => `${paper.documentTitle} ${paper.apNumber} ${paper.documentType}`)
  ].join(" "));
}

function finalSearchBlob(item) {
  return normalize([
    item.title,
    getHebrewTopicTitle(item),
    getHebrewSummary(item),
    getCommitteeView(item),
    item.standard,
    ...(item.standards || []),
    item.fullText || "",
    ...(item.relatedPapers || []).map((paper) => `${paper.apNumber} ${paper.documentTitle}`),
    ...(item.tags || [])
  ].join(" "));
}

function getMatchingSnippet(item, query) {
  if (!query) return "";

  const rawText = String(item.fullText || "").replace(/\s+/g, " ").trim();
  if (!rawText) return "";

  const normalizedText = normalize(rawText);
  const hitIndex = normalizedText.indexOf(query);
  if (hitIndex === -1) return "";

  const start = Math.max(0, hitIndex - 90);
  const end = Math.min(rawText.length, hitIndex + query.length + 130);
  const prefix = start > 0 ? "..." : "";
  const suffix = end < rawText.length ? "..." : "";
  return `${prefix}${rawText.slice(start, end).trim()}${suffix}`;
}

function createBadge(text, tone = "neutral") {
  const badge = document.createElement("span");
  badge.className = `badge badge-${tone}`;
  badge.textContent = text;
  return badge;
}

function createEmptyState(message) {
  const empty = document.createElement("div");
  empty.className = "empty-state";
  empty.textContent = message;
  return empty;
}

function updateStatus({ label, count, value, note }) {
  statusLabel.textContent = label;
  statusCount.textContent = String(count);
  statusValue.textContent = value;
  statusNote.textContent = note;
}

function populateSelect(select, options, allLabel, labels = {}) {
  select.innerHTML = "";

  const allOption = document.createElement("option");
  allOption.value = "all";
  allOption.textContent = allLabel;
  select.appendChild(allOption);

  options.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = labels[value] || value;
    select.appendChild(option);
  });
}

function createCardShell() {
  const article = document.createElement("article");
  article.className = "tracker-card";
  return article;
}

function createMetaLine(parts) {
  const wrap = document.createElement("div");
  wrap.className = "card-meta";
  parts.filter(Boolean).forEach((part) => {
    const label = document.createElement("span");
    const isCode = /^(?:IFRS|IAS|IFRIC|IASB|SIC|AP\s?\d)/.test(part);
    label.className = isCode ? "meta-pill meta-code" : "meta-pill";
    label.dir = isCode ? "ltr" : "auto";
    label.textContent = part;
    wrap.appendChild(label);
  });
  return wrap;
}

function createActionButton(label, onClick, className = "ghost-button") {
  const button = document.createElement("button");
  button.type = "button";
  button.className = className;
  button.textContent = label;
  button.addEventListener("click", onClick);
  return button;
}

function openItemModal(item, { focusPapers = false } = {}) {
  const reviewed = reviewedIds.has(item.id);
  const relatedPapers = item.relatedPapers || [];
  const isFinal = Boolean(item.finalAgendaDecisionUrl);

  modalMeta.innerHTML = "";
  modalMeta.appendChild(createBadge(item.standards?.join(" · ") || item.standard || item.group || "IFRIC"));
  modalMeta.appendChild(createBadge(item.status || "החלטה סופית", getStatusTone(item.status || "neutral")));
  if (item.apNumber) {
    modalMeta.appendChild(createBadge(item.apNumber, "neutral"));
  }

  modalTitle.textContent = getHebrewTopicTitle(item);
  modalSubtitle.textContent = [
    item.topicTitleEn || item.title || "",
    item.meetingDate ? `מועד: ${formatDate(item.meetingDate)}` : item.publishedAt ? `פורסם: ${decisionDate(item)}` : "",
    item.documentType ? `סוג מסמך: ${item.documentType}` : ""
  ].filter(Boolean).join(" | ");

  modalSummary.textContent = getHebrewSummary(item);
  modalProposalSection.hidden = !item.summaryProposalHe;
  modalProposal.textContent = item.summaryProposalHe || "";

  modalStaffSection.hidden = !item.staffViewHe;
  modalStaffView.textContent = item.staffViewHe || "";

  const committeeView = getCommitteeView(item);
  modalCommitteeSection.hidden = !committeeView;
  modalCommitteeView.textContent = committeeView;

  modalLinks.innerHTML = "";
  [
    ["דף הפגישה", item.meetingUrl],
    ["נייר עבודה", item.documentUrl],
    ["החלטה סופית", item.finalAgendaDecisionUrl],
    ["החלטת סדר יום מוצעת", item.tentativeAgendaDecisionUrl],
    ["מסמכי התייעצות", item.consultationUrl],
    ["עדכון על מעמד ההחלטה", item.historyUrl],
    ["IFRIC Update", item.ifricUpdateUrl],
    ["המקור הרשמי", item.sourceUrl]
  ].filter(([, url], index, links) => url && links.findIndex(([, candidate]) => candidate === url) === index).forEach(([label, url]) => {
    const link = document.createElement("a");
    link.href = url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.className = "link-chip";
    link.textContent = label;
    modalLinks.appendChild(link);
  });

  modalRelated.innerHTML = "";
  modalRelatedHeading.textContent = isFinal ? "ניירות עבודה שקדמו להחלטה" : "מסמכים קשורים";
  if (!relatedPapers.length) {
    const message = isFinal ? "טרם נמצא קישור מאומת לנייר עבודה עבור החלטה זו." : "לא נמצאו מסמכים קשורים עבור הפריט הזה.";
    modalRelated.appendChild(createEmptyState(message));
  } else {
    relatedPapers.forEach((paper) => {
      const row = document.createElement("article");
      row.className = "related-paper";

      const head = document.createElement("div");
      head.className = "related-paper-head";
      head.appendChild(createBadge(paperKind[paper.relationshipType] || "מסמך קשור", getDocumentTone(paper.documentType || "")));
      if (paper.apNumber) {
        head.appendChild(createBadge(paper.apNumber, "neutral"));
      }
      if (paper.needsReview) {
        head.appendChild(createBadge("דורש בדיקה", "review"));
      }

      const title = document.createElement("h4");
      title.textContent = paper.documentTitle;
      title.dir = "auto";

      const meta = document.createElement("p");
      meta.className = "related-paper-meta";
      meta.textContent = [
        paper.documentType,
        paper.meetingDate ? formatDate(paper.meetingDate) : "",
        paper.confidenceScore ? `ביטחון ${paper.confidenceScore}` : ""
      ].filter(Boolean).join(" | ");

      row.appendChild(head);
      row.appendChild(title);
      row.appendChild(meta);

      const sources = document.createElement("div");
      sources.className = "source-links";
      for (const [label, url] of [["פתח מסמך", paper.documentUrl], ["דף הפגישה", paper.sourcePageUrl]]) {
        if (!url) continue;
        const link = document.createElement("a");
        link.href = url;
        link.target = "_blank";
        link.rel = "noreferrer";
        link.className = "source-link";
        link.textContent = label;
        sources.appendChild(link);
      }
      if (sources.children.length) row.appendChild(sources);

      modalRelated.appendChild(row);
    });
  }

  modalReviewed.textContent = reviewed ? "סומן כנבדק" : "סמן כנבדק";
  modalReviewed.dataset.itemId = item.id;
  if (!modal.open) {
    modal.showModal();
    modal.scrollTop = 0;
  }
  if (focusPapers) {
    modalRelatedHeading.focus({ preventScroll: true });
    modalRelatedHeading.scrollIntoView({ block: "start" });
  }
}

function renderTrackerCards(grid, items, summaryElement, summaryText) {
  grid.innerHTML = "";
  summaryElement.textContent = summaryText;

  if (!items.length) {
    grid.appendChild(createEmptyState("לא נמצאו נושאים מתאימים."));
    return;
  }

  items.forEach((item) => {
    const article = createCardShell();
    article.appendChild(createMetaLine([
      item.group,
      item.meetingDate ? formatDate(item.meetingDate) : "",
      item.apNumber,
      item.standards?.join(" · ") || item.standard
    ]));

    const title = document.createElement("h3");
    title.className = "card-title";
    title.textContent = getHebrewTopicTitle(item);

    const subtitle = document.createElement("p");
    subtitle.className = "card-subtitle";
    subtitle.dir = "ltr";
    subtitle.textContent = item.topicTitleEn;
    subtitle.hidden = title.textContent === subtitle.textContent;

    const badgeRow = document.createElement("div");
    badgeRow.className = "card-badges";
    badgeRow.appendChild(createBadge(item.status, getStatusTone(item.status)));
    if (item.automaticHe?.summaryHe) badgeRow.appendChild(createBadge("תקציר בתרגום אוטומטי"));
    if (item.paperPending) badgeRow.appendChild(createBadge("נייר עבודה טרם פורסם", "tentative"));
    if (item.needsReview) {
      badgeRow.appendChild(createBadge("דורש בדיקה", "review"));
    }
    if (reviewedIds.has(item.id)) {
      badgeRow.appendChild(createBadge("נבדק מקומית", "progress"));
    }

    const summary = document.createElement("p");
    summary.className = "card-summary";
    summary.textContent = getHebrewSummary(item);
    const milestone = document.createElement("p");
    milestone.className = "card-milestone";
    const milestoneLabel = milestones[item.nextMilestone] || item.nextMilestone;
    const deadline = item.commentDate && item.commentDate >= localToday()
      ? `תגובות עד ${formatDate(item.commentDate)}` : "";
    const target = item.milestoneDate && item.milestoneDate >= localToday()
      ? new Intl.DateTimeFormat("he-IL", { month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(item.milestoneDate)) : "";
    milestone.textContent = [milestoneLabel && `הצעד הבא: ${milestoneLabel}${target ? ` (${target}, משוער)` : ""}`, deadline].filter(Boolean).join(" · ");
    milestone.hidden = !milestone.textContent;

    const footer = document.createElement("div");
    footer.className = "card-actions";
    footer.appendChild(createActionButton("פרטים", () => openItemModal(item)));
    if (item.documentUrl || item.sourceUrl) {
      const link = document.createElement("a");
      link.href = item.documentUrl || item.sourceUrl;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.className = "ghost-button";
      link.textContent = item.documentUrl ? "נייר עבודה" : "מקור רשמי";
      footer.appendChild(link);
    }

    article.append(title, subtitle, badgeRow, summary, milestone, footer);
    grid.appendChild(article);
  });
}

function renderFinalCards(grid, items, summaryElement, query) {
  grid.innerHTML = "";
  summaryElement.textContent = `${items.length} החלטות סופיות מוצגות.`;

  if (!items.length) {
    grid.appendChild(createEmptyState("לא נמצאו החלטות סופיות מתאימות."));
    return;
  }

  items.forEach((item) => {
    const article = createCardShell();
    article.appendChild(createMetaLine([
      decisionDate(item),
      item.standards?.join(" · ") || item.standard
    ]));

    const title = document.createElement("h3");
    title.className = "card-title";
    title.textContent = getHebrewTopicTitle(item);

    const subtitle = document.createElement("p");
    subtitle.className = "card-subtitle";
    subtitle.dir = "ltr";
    subtitle.textContent = item.title;
    subtitle.hidden = title.textContent === subtitle.textContent;

    const badgeRow = document.createElement("div");
    badgeRow.className = "card-badges";
    const paperCount = item.relatedPapers?.length || 0;
    if (!paperCount) badgeRow.appendChild(createBadge("טרם נמצא נייר עבודה"));
    if (item.needsReview) {
      badgeRow.appendChild(createBadge("דורש בדיקה", "review"));
    }
    if (item.automaticHe?.summaryHe) badgeRow.appendChild(createBadge("תקציר בתרגום אוטומטי"));
    if (item.withdrawalDate) badgeRow.appendChild(createBadge(`משיכה מ־${formatDate(item.withdrawalDate)}`, "review"));
    else if (item.historyNoteHe) badgeRow.appendChild(createBadge("נמשכה על ידי IASB", "review"));
    else if (item.archiveOnly) badgeRow.appendChild(createBadge("רשומה היסטורית"));

    const summary = document.createElement("p");
    summary.className = "card-summary";
    summary.textContent = item.historyNoteHe || getHebrewSummary(item);

    const snippet = getMatchingSnippet(item, normalize(query));
    let snippetElement = null;
    if (snippet) {
      snippetElement = document.createElement("p");
      snippetElement.className = "decision-snippet";
      snippetElement.textContent = snippet;
    }

    const footer = document.createElement("div");
    footer.className = "card-actions";
    footer.appendChild(createActionButton("פרטים", () => openItemModal(item)));
    if (paperCount) {
      footer.appendChild(createActionButton(`ניירות עבודה (${paperCount})`, () => openItemModal(item, { focusPapers: true })));
    }

    const link = document.createElement("a");
    link.href = item.sourceUrl;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.className = "ghost-button";
    link.textContent = "פתח החלטה";
    footer.appendChild(link);

    article.append(title, subtitle, badgeRow, summary);
    if (snippetElement) article.appendChild(snippetElement);
    article.appendChild(footer);
    grid.appendChild(article);
  });
}

function renderUpdateCards(grid, items, summaryElement, total) {
  grid.innerHTML = "";
  summaryElement.textContent = `${items.length} מתוך ${total} עדכונים`;

  if (!items.length) {
    grid.appendChild(createEmptyState("לא נמצאו עדכונים מתאימים."));
    return;
  }

  items.forEach((item) => {
    const article = createCardShell();
    article.appendChild(createMetaLine([
      item.group,
      formatDate(item.changedAt),
      changeLabels[item.changeType]
    ]));

    const title = document.createElement("h3");
    title.className = "card-title";
    const topic = itemsById.get(item.itemId);
    title.textContent = topic ? getHebrewTopicTitle(topic) : item.topicTitleEn;

    const footer = document.createElement("div");
    footer.className = "card-actions";
    if (topic) {
      footer.appendChild(createActionButton("פרטים", () => openItemModal(topic)));
    } else if (item.sourceUrl) {
      const link = document.createElement("a");
      link.href = item.sourceUrl;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.className = "ghost-button";
      link.textContent = "מקור רשמי";
      footer.appendChild(link);
    }

    article.append(title, footer);
    grid.appendChild(article);
  });
}

function matchesStandard(item, standard) {
  return standard === "all" || (item?.standards || []).includes(standard);
}

function buildHomeResults() {
  const query = normalize(globalSearch.value);
  const standard = homeStandard.value || "all";
  const filtered = Boolean(query) || standard !== "all";
  const today = localToday();
  const upcoming = monitor.scheduled.filter((item) => item.meetingEndDate >= today);
  const nextDate = [...upcoming].map((item) => item.meetingDate).sort()[0];
  const discussions = filtered
    ? [...monitor.scheduled, ...monitor.active].filter((item) => matchesStandard(item, standard) && (!query || trackerSearchBlob(item).includes(query)))
    : nextDate ? upcoming.filter((item) => item.meetingDate === nextDate) : monitor.active.slice(0, 6);
  const finals = filtered
    ? ifricDecisions.filter((item) => matchesStandard(item, standard) && (!query || finalSearchBlob(item).includes(query)))
    : ifricDecisions.slice(0, 6);
  const changes = filtered ? monitor.changes.filter((change) => {
    const item = itemsById.get(change.itemId);
    return matchesStandard(item, standard) && (!query || normalize(change.topicTitleEn).includes(query) ||
      Boolean(item && (item.finalAgendaDecisionUrl ? finalSearchBlob(item) : trackerSearchBlob(item)).includes(query)));
  }) : monitor.changes;

  homeClear.disabled = !filtered;
  homeLatestTitle.textContent = filtered ? "דיונים ופרויקטים" : nextDate ? "לקראת הדיון הבא" : "נושאים פעילים";
  homeFinalTitle.textContent = filtered ? "החלטות תואמות" : "החלטות אחרונות";
  renderTrackerCards(homeHighlights, discussions, homeSummary,
    filtered ? `${discussions.length} תוצאות` : nextDate ? `${formatDate(nextDate)} · ${discussions.length} נושאים בסדר היום` : "מתוך תוכנית העבודה");
  renderFinalCards(homePending, finals, homePendingSummary, query);
  homeActivity.hidden = filtered && !changes.length;
  homeLayout.classList.toggle("is-searching", homeActivity.hidden);
  if (!homeActivity.hidden) {
    renderUpdateCards(homeUpdates, showAllUpdates ? changes : changes.slice(0, 3), homeUpdatesSummary, changes.length);
    homeMoreUpdates.hidden = changes.length <= 3;
    homeMoreUpdates.textContent = showAllUpdates ? "הצג פחות" : "עוד עדכונים";
    homeMoreUpdates.setAttribute("aria-expanded", String(showAllUpdates));
  }
  updateStatus({
    label: filtered ? "תוצאות חיפוש וסינון" : "תמונת מצב",
    count: filtered ? discussions.length + finals.length : monitor.active.length,
    value: filtered ? "תוצאות" : "פרויקטים ונושאים פעילים",
    note: monitor.generatedAt ? `נבדק מול המקורות ב־${formatDate(monitor.generatedAt)}${monitor.translationIssue ? " · יש תרגומים שממתינים לעיבוד" : ""}` : "טוען נתונים..."
  });
}

function renderFinalsTab() {
  const query = normalize(controls.finals.search.value);
  const standard = controls.finals.standard.value;

  const items = ifricDecisions
    .filter((item) => matchesStandard(item, standard))
    .filter((item) => !query || finalSearchBlob(item).includes(query))
    .sort((a, b) => new Date(b.publishedAt) - new Date(a.publishedAt));

  renderFinalCards(controls.finals.grid, items, controls.finals.summary, query);
  controls.finals.clear.disabled = !query && standard === "all";

  if (activeTab === "finals") {
    updateStatus({
      label: "החלטות סופיות",
      count: ifricDecisions.length,
      value: `${items.length} החלטות מוצגות`,
      note: "החיפוש בלשונית זו כולל גם חיפוש בתוך הטקסט המלא של ההחלטות הסופיות."
    });
  }
}

function renderTopicsTab() {
  const query = normalize(controls.topics.search.value);
  const standard = controls.topics.standard.value;
  const status = controls.topics.status.value;
  const group = controls.topics.group.value;
  const matches = (item) => matchesStandard(item, standard) &&
    (status === "all" || item.stage === status) && (group === "all" || item.group === group) &&
    (!query || trackerSearchBlob(item).includes(query));
  const meetings = monitor.scheduled.filter(matches).sort((left, right) => right.meetingDate.localeCompare(left.meetingDate));
  const projects = monitor.active.filter(matches);
  controls.topics.clear.disabled = !query && standard === "all" && status === "all" && group === "all";
  controls.topics.summary.textContent = "פגישות קרובות ואחרונות";
  renderTrackerCards(controls.topics.meetings, meetings, controls.topics.meetingSummary, `${meetings.length} נושאים בפגישות`);
  renderTrackerCards(controls.topics.grid, projects, controls.topics.projectSummary, `${projects.length} פרויקטים`);
  if (activeTab === "topics") {
    updateStatus({
      label: "על הפרק", count: projects.length, value: "פרויקטים בתצוגה",
      note: `${meetings.length} נושאים בסדרי יום. מועדי הפרסום בתוכנית העבודה הם משוערים.`
    });
  }
}

function activateTab(tabName) {
  activeTab = tabName;
  [pageTitle.textContent, pageDescription.textContent] = pageCopy[tabName];

  tabButtons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.tab === tabName);
    if (button.dataset.tab === tabName) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });

  tabPanels.forEach((panel) => {
    panel.hidden = panel.dataset.tabPanel !== tabName;
  });

  if (tabName === "home") {
    buildHomeResults();
    return;
  }

  if (tabName === "finals") renderFinalsTab();
  if (tabName === "topics") renderTopicsTab();
}

tabButtons.forEach((button) => {
  button.addEventListener("click", () => activateTab(button.dataset.tab));
});
document.querySelectorAll("[data-open-tab]").forEach((button) => {
  button.addEventListener("click", () => {
    const destination = button.dataset.openTab;
    if (activeTab === "home" && controls[destination] && homeStandard.value) {
      const select = controls[destination].standard;
      select.value = [...select.options].some((option) => option.value === homeStandard.value) ? homeStandard.value : "all";
    }
    activateTab(destination);
    const tab = tabButtons.find((entry) => entry.dataset.tab === destination);
    tab?.focus();
    tab?.scrollIntoView({ block: "nearest" });
  });
});

modalReviewed.addEventListener("click", () => {
  const { itemId } = modalReviewed.dataset;
  if (!itemId) return;

  if (reviewedIds.has(itemId)) {
    reviewedIds.delete(itemId);
  } else {
    reviewedIds.add(itemId);
  }

  persistReviewedIds();

  const trackerItem = itemsById.get(itemId);
  if (trackerItem) {
    openItemModal(trackerItem);
  }

  activateTab(activeTab);
});

globalSearch.addEventListener("input", buildHomeResults);
homeStandard.addEventListener("change", buildHomeResults);
homeClear.addEventListener("click", () => {
  globalSearch.value = "";
  homeStandard.value = "all";
  buildHomeResults();
  globalSearch.focus();
});
homeMoreUpdates.addEventListener("click", () => {
  showAllUpdates = !showAllUpdates;
  buildHomeResults();
});

[
  ["finals", renderFinalsTab],
  ["topics", renderTopicsTab]
].forEach(([key, render]) => {
  Object.values(controls[key]).forEach((control) => {
    if (control instanceof HTMLElement && (control.tagName === "INPUT" || control.tagName === "SELECT")) {
      control.addEventListener("input", render);
      control.addEventListener("change", render);
    }
  });

  if (controls[key].clear) {
    controls[key].clear.addEventListener("click", () => {
      Object.values(controls[key]).forEach((control) => {
        if (!(control instanceof HTMLElement)) return;
        if (control.tagName === "INPUT") control.value = "";
        if (control.tagName === "SELECT") control.value = "all";
      });
      render();
    });
  }
});

async function loadJson(path) {
  const candidates = [
    new URL(path, window.location.href).toString(),
    new URL(path.replace(/^\.\//, ""), `${window.location.origin}${window.location.pathname.endsWith("/") ? window.location.pathname : `${window.location.pathname}/`}`).toString()
  ];

  let lastError = null;

  for (const candidate of candidates) {
    try {
      const response = await fetch(candidate, { cache: "no-store" });
      if (response.ok) {
        return response.json();
      }
      lastError = new Error(`Failed to load ${candidate} (${response.status})`);
    } catch (error) {
      lastError = error;
    }
  }

  throw lastError || new Error(`Failed to load ${path}`);
}

function mergeFinalDecisionMetadata(decision) {
  return {
    ...decision,
    topicTitleEn: decision.title,
    group: "IFRIC",
    standards: decision.standards || [decision.standard].filter(Boolean),
    status: "החלטת סדר יום סופית",
    finalAgendaDecisionUrl: decision.sourceUrl
  };
}

async function initialize() {
  const [ifricRaw, snapshot] = await Promise.all([
    loadJson("./data/ifric.json"),
    loadJson("./data/ifrs-monitor.json")
  ]);
  monitor = { ...snapshot, active: snapshot.active.map(asDiscussion), scheduled: snapshot.scheduled.map(asDiscussion) };

  ifricDecisions = ifricRaw
    .map(mergeFinalDecisionMetadata)
    .sort((a, b) => new Date(b.publishedAt) - new Date(a.publishedAt));

  const discussions = [...monitor.active, ...monitor.scheduled];
  const items = [...discussions, ...ifricDecisions];
  itemsById = new Map(items.map((item) => [item.id, item]));
  const standardOptions = (records) => sortStandards([...new Set(records.flatMap((item) => item.standards || []))]);
  populateSelect(homeStandard, standardOptions(items), "כל התקנים");
  populateSelect(controls.topics.standard, standardOptions(discussions), "כל התקנים");
  populateSelect(
    controls.topics.status,
    [...new Set(discussions.map((item) => item.stage))],
    "כל השלבים", { ...stageLabels, feedback: "בבחינת תגובות" }
  );
  populateSelect(controls.topics.group, ["IFRIC", "IASB"], "שני הגופים");
  populateSelect(controls.finals.standard, standardOptions(ifricDecisions), "כל התקנים");

  activateTab(activeTab);
}

initialize().catch((error) => {
  console.error(error);
  updateStatus({
    label: "שגיאת טעינה",
    count: 0,
    value: "הנתונים לא נטענו",
    note: "בדוק שקבצי JSON קיימים בתיקיית data ושהאתר רץ דרך השרת המקומי."
  });
  homeSummary.textContent = `טעינת הנתונים נכשלה. ${error?.message || ""}`.trim();
});

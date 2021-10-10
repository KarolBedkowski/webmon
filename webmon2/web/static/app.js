/*
 * app.js
 * Copyright (C) 2019-2021 Karol Będkowski
 *
 * Distributed under terms of the GPLv3 license.
 */
(function() {
	'use strict';

	function _create_question_link(label, callback) {
		let element = document.createElement("a");
		element.href = "#";
		element.appendChild(document.createTextNode(label));
		element.onclick = (event) => {
			event.preventDefault();
			callback();
		};
		return element;
	}

	function handleConfirm(event) {
		event.preventDefault();
		let eventTarget = event.target;
		let question = eventTarget.dataset.question;
		let targetParent = eventTarget.parentNode;

		eventTarget.style.display = "none";

		let yesElement = _create_question_link("yes", (event) => {
			document.location.href = eventTarget.href;
		});

		let noElement = _create_question_link("no", (event) => {
			eventTarget.style.display = "";
			questionElement.remove();
		});

		let questionElement = document.createElement("span");
		questionElement.className = "confirm";
		questionElement.append(document.createTextNode(question));
		questionElement.append(document.createTextNode(" "));
		questionElement.append(yesElement);
		questionElement.append(document.createTextNode(" "));
		questionElement.append(noElement);
		targetParent.append(questionElement);
	}

	function executeEntryAction(url, formData, onDataCallback, onFinishCallback) {
		let csrfToken = getMetaValue("_app_csrf");
		formData.append("_csrf_token", csrfToken);
		fetch(url, {
			method: "POST",
			body: formData,
		}).then((resp) => {
			let csrf = resp.headers.get("X-CSRF-TOKEN");
			if (csrf) {
				document.querySelector("meta[name=_app_csrf]").setAttribute("value", csrf);
			}
			return resp.json();
		}).then((data) => {
			if (onDataCallback) onDataCallback(data);
			if (onFinishCallback) onFinishCallback();
		}).catch((error) => {
			window.console.log(error);
			if (onFinishCallback) onFinishCallback();
		});
	}

	function getMetaValue(key) {
		let element = document.querySelector("meta[name=" + key + "]");
		return (element !== null) ? element.getAttribute("value") : null;
	}

	document.addEventListener("DOMContentLoaded", function() {
		let mark_read_url = getMetaValue("_app_entry_mark_read_api");
		document.querySelectorAll("a[data-action=mark_read]").forEach((element) => {
			element.onclick = (event) => {
				event.preventDefault();
				if (element.attributes.processing) return;
				element.attributes.processing = true;

				let formData = new FormData();
				let article = element.closest('article');
				formData.append("entry_id", article.dataset["entryId"]);
				formData.append("value", (article.dataset["state"] == "read") ? "unread": "read");

				executeEntryAction(mark_read_url, formData, (data) => {
					if (data.result == "read" || data.result == "unread") {
						article.dataset["state"] = data.result;
					}
					let num_count = data.unread;
					let num_field = document.getElementById("entries_unread_cnt");
					if (num_count > 0) {
						num_field.innerHTML = "(" + num_count + ")";
					} else {
						num_field.innerHTML = "";
					}
				}, () => {
					element.attributes.processing = false;
				});
			};
		});
		let mark_star_url = getMetaValue("_app_mark_star_api");
		document.querySelectorAll("a[data-action=mark_star]").forEach((element) => {
			element.onclick = (event) => {
				event.preventDefault();
				if (element.attributes.processing) return;
				element.attributes.processing = true;

				let formData = new FormData();
				let article = element.closest('article');
				formData.append("entry_id", article.dataset["entryId"]);
				formData.append("value", (article.dataset["starred"] == "star") ? "unstar" : "star");

				executeEntryAction(mark_star_url, formData, (data) => {
					if (data.result == "star" || data.result == "unstar") {
						article.dataset["starred"] = data.result;
					}
				}, () => {
					element.attributes.processing = false;
				});
			};
		});
		document.querySelectorAll("a[data-req-confirm=yes]").forEach((element) => {
			element.onclick = handleConfirm;
		});

		document.querySelectorAll("a[data-action=hist-back]").forEach((element) => {
			element.onclick = (event) => {
				event.preventDefault();
				window.history.back();
		}});

		function getArticleIds() {
			let articlesId = []
			document.querySelectorAll("article[data-entry-id]").forEach((element) => {
				articlesId.push(element.dataset.entryId);
			});
			return articlesId;
		}

		document.querySelectorAll("a[data-action=mark-all-read]").forEach((element) => {
			element.onclick = (event) => {
				event.preventDefault();
				let articlesId = getArticleIds().join(",");
				let url = element.attributes.href.value + "&ids=" + articlesId;
				window.location.href = url;
		}});

		document.querySelectorAll("time").forEach((element) => {
			if (element.title != undefined) {
				element.onclick = (event) => {
					element.innerHTML = element.getAttribute('title');
				};
			}
		});
	});

})();

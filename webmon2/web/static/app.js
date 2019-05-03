/*
 * app.js
 * Copyright (C) 2019 Karol Będkowski
 *
 * Distributed under terms of the GPLv3 license.
 */
(function() {
	'use strict';

	function executeEntryAction(url, formData, onDataCallback, onFinishCallback) {
		fetch(url, {
			method: "POST",
			body: formData,
		}).then((resp) => {
			return resp.text();
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
					if (data == "read" || data == "unread") {
						article.dataset["state"] = data;
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
					if (data == "star" || data == "unstar") {
						article.dataset["starred"] = data;
					}
				}, () => {
					element.attributes.processing = false;
				});
			};
		});
		document.querySelectorAll("a[data-req-confirm=yes]").forEach((element) => {
			element.onclick = (event) => {
				if (!confirm("Realy?")) {
					event.preventDefault()
				}
			};
		});
	});

})();

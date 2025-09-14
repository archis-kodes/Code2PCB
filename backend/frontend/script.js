document.getElementById("uploadForm").addEventListener("submit", async (e) => {
    e.preventDefault();

    const fileInput = document.getElementById("fileInput");
    if (!fileInput.files.length) {
        alert("Please select a .ino file!");
        return;
    }

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);

    document.getElementById("status").innerText = "⏳ Uploading and compiling...";

    try {
        const response = await fetch("/upload", {
            method: "POST",
            body: formData
        });

        const result = await response.json();

        if (result.status === "success") {
            window.location.href = `result.html?status=success&chip=${result.chip}&gerber=${result.gerber}`;
        } else {
            window.location.href = "result.html?status=fail";
        }

    } catch (err) {
        document.getElementById("status").innerText = "❌ Error: " + err.message;
    }
});

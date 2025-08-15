const plot_ctx = document.getElementById("current_plot").getContext("2d");
const current_plot = new Chart(plot_ctx, {
    type: "line",
    data: {
        labels: [],
        datasets: [{
            data: [],
            borderColor: "oklch(0.77 0.152 181.912)",
            borderWidth: 2,
            pointStyle: false,
        }],
    },
    options: {
        animation: false,
        plugins: { legend: { display: false } },
        scales: {
            x: {
                display: true, title: {
                    display: true,
                    text: "Time (s)"
                }
            },
            y: {
                display: true, title: {
                    display: true,
                    text: "Current (mA)"
                }
            },
        },
        maintainAspectRatio: false,
        responsive: true,
    },
});

if (window.script_config.enable_audio) {
    var celebrate_audio = new Audio("/static/celebrate.ogg");
}

function celebrate() {
    var s = htmx.find("#glitch_success_div")
    htmx.removeClass(s, "invisible");
    htmx.removeClass(s, "opacity-0");
    if (window.script_config.enable_audio) {
        celebrate_audio.play();
    }
}

function stop_celebrate() {
    var s = htmx.find("#glitch_success_div")
    htmx.addClass(s, "invisible");
    htmx.addClass(s, "opacity-0");
}

const current_trace = [];
for (let x = 0; x < window.script_config.n_current_samples; x++) {
    current_plot.data.labels.push(x / window.script_config.current_sampling_rate);
    current_trace.push(0);
}

const logs_output = document.getElementById("logs_output")
const logs_data = [];

const serial_output = document.getElementById("serial_output")
const serial_data = [];

var ws = new WebSocket(`ws://${location.host}/ws`);

ws.onmessage = function (event) {
    msg = JSON.parse(event.data);

    if ("current" in msg) {
        current_trace.shift();
        current_trace.push(msg.current);

        current_plot.data.datasets[0].data = current_trace;
        current_plot.update();
    }

    else if ("log" in msg) {
        if (logs_data.length > 32) {
            logs_data.shift();
        }
        if (msg.log.level == "ERROR") {
            color = "text-error";
        } else if (msg.log.level == "WARNING") {
            color = "text-warning";
        } else if (msg.log.level == "CRITICAL") {
            color = "text-error-content";
        } else {
            color = "text-base-100";
        }
        logs_data.push(`<span class="text-info">[${msg.log.date}]</span> <span class="${color}">[${msg.log.level}] ${msg.log.message}</span>`);
        logs_output.innerHTML = logs_data.join("<br/>");
        logs_output.scrollTop = logs_output.scrollHeight;
    }

    else if ("serial" in msg) {
        if (serial_data.length > 32) {
            serial_data.shift();
        }
        serial_data.push(msg.serial)
        serial_output.innerHTML = "<pre>" + serial_data.join("") + "</pre>";
        serial_output.scrollTop = serial_output.scrollHeight;
    }

    else if ("action" in msg) {
        if (msg.action == "success") {
            setTimeout(celebrate, 0);
            setTimeout(stop_celebrate, 6000);
        }
        else if (msg.action == "pulse") {
            play_pewpew_sound();
        }
        else if (msg.action == "set_pulse_counter") {
            document.getElementById("pulse_counter").innerText = msg.value;
        }
        else if (msg.action == "set_success_counter") {
            document.getElementById("success_counter").innerText = msg.value;
        }
        else if (msg.action == "enable_pulse_button") {
            htmx.removeClass(htmx.find("#pulse_button"), "btn-disabled");
        }
        else if (msg.action == "disable_pulse_button") {
            htmx.addClass(htmx.find("#pulse_button"), "btn-disabled");
        }
        else if (msg.action == "enable_reset_button") {
            htmx.removeClass(htmx.find("#reset_button"), "btn-disabled");
        }
        else if (msg.action == "disable_reset_button") {
            htmx.addClass(htmx.find("#reset_button"), "btn-disabled");
        }
        else if (msg.action == "set_serial_disconnected") {
            var s_conn = htmx.find("#serial_status_connected")
            var s_disconn = htmx.find("#serial_status_disconnected")
            htmx.addClass(s_conn, "hidden");
            htmx.removeClass(s_disconn, "hidden");
        }
        else if (msg.action == "set_serial_connected") {
            var s_conn = htmx.find("#serial_status_connected")
            var s_disconn = htmx.find("#serial_status_disconnected")
            htmx.addClass(s_disconn, "hidden");
            htmx.removeClass(s_conn, "hidden");
        }
        else if (msg.action == "set_target_power_disabled") {
            var s_en = htmx.find("#power_status_enabled")
            var s_dis = htmx.find("#power_status_disabled")
            htmx.addClass(s_en, "hidden");
            htmx.removeClass(s_dis, "hidden");
        }
        else if (msg.action == "set_target_power_enabled") {
            var s_en = htmx.find("#power_status_enabled")
            var s_dis = htmx.find("#power_status_disabled")
            htmx.addClass(s_dis, "hidden");
            htmx.removeClass(s_en, "hidden");
        }
        else if (msg.action == "refresh_coordinates") {
            htmx.ajax("GET", "/stage", { "target": "#stage_coordinates_card" });
        }
        else if (msg.action == "set_target_en_toggle_off") {
            htmx.find("#target_en_toggle").checked = false;
        }
    }
};

const microscope_view = document.getElementById("microscope_view");

microscope_view.onkeydown = function (e) {
    switch (e.key) {
        case "ArrowUp":
        case "8":
            htmx.ajax("GET", "/stage/up", { "swap": "none" });
            break;
        case "ArrowDown":
        case "2":
            htmx.ajax("GET", "/stage/down", { "swap": "none" });
            break;
        case "ArrowLeft":
        case "4":
            htmx.ajax("GET", "/stage/left", { "swap": "none" });
            break;
        case "ArrowRight":
        case "6":
            htmx.ajax("GET", "/stage/right", { "swap": "none" });
            break;
    }
};

microscope_view.addEventListener("wheel", function (event) {
    event.preventDefault();

    if (event.deltaY < 0) {
        htmx.ajax("GET", "/stage/in", { "swap": "none" });
    } else if (event.deltaY > 0) {
        htmx.ajax("GET", "/stage/out", { "swap": "none" });
    }
});


if (window.script_config.enable_audio) {
    var pewpew_audio = new Audio("/static/laser.ogg");
}

function play_pewpew_sound() {
    if (window.script_config.enable_audio) {
        pewpew_audio.currentTime = 0;
        pewpew_audio.play();
    }
}
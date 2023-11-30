var video = document.getElementById('video');
var alertElement = document.getElementById('alert');

var ws = new WebSocket('ws://localhost:8000/ws');

// 알럿창 초기 숨기기
// alertElement.style.display = 'none';
// alert.textContent = 'none';

ws.onmessage = function(event) {
    var data = JSON.parse(event.data);
    var blob = data.image;
    blob = atob(blob)
    var bytes = new Uint8Array(blob.length);
    for (var i = 0; i < blob.length; i++) {
        bytes[i] = blob.charCodeAt(i);
    }
    var blob = new Blob([bytes.buffer], { type: 'image/jpeg' });
    var url = URL.createObjectURL(blob);
    video.src = url;

    // 디텍션 결과에 따라 알림 메시지 업데이트 및 표시/숨김
    if (data.detection.includes('person')) {
        alertElement.textContent = '사람이 감지되었습니다!';
        alertElement.style.color = 'red';
        alertElement.style.display = 'block';  // 알림 보이기
    } else {
        alertElement.textContent = '감지된 사람이 없습니다.';
        alertElement.style.color = 'green';
        alertElement.style.display = 'none';  // 알림 숨기기
    }

    // // 디텍션 결과에 따라 알림 창 표시
    // if (data.detection.includes('person')) {
    //     alert('사람이 감지되었습니다!');
    // } else {
    //     // 사람이 감지되지 않았을 때는 알림 창을 표시하지 않습니다.
    //     // alert('감지된 사람이 없습니다.');
    // }
};

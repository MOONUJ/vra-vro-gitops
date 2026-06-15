#!/bin/bash

# Cloud-init 네트워크 설정에서 IP 주소 교체 스크립트 (sudo 명령어 방식)

set -euo pipefail

# 권한 체크 없이 필요한 곳에서 sudo 사용

# ========================================
# 설정 변수 (여기서 IP 주소를 미리 지정)
# ========================================
OLD_IP="replaceOldIp"    # 교체할 기존 IP
NEW_IP="replaceNewIp"    # 새로 설정할 IP

# 파일 경로
NETWORK_CONFIG_FILE="/etc/cloud/cloud.cfg.d/99_network.cfg"

# 색상 코드
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로그 함수
log() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] ${BLUE}INFO${NC}: $1" >&2
}

warn() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] ${YELLOW}WARN${NC}: $1" >&2
}

error() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] ${RED}ERROR${NC}: $1" >&2
}

success() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] ${GREEN}SUCCESS${NC}: $1" >&2
}

# 에러 처리 함수
error_exit() {
    error "$1"
    exit 1
}

# IP 주소 형식 검증
validate_ip() {
    local ip="$1"
    local description="$2"
    
    # IP 주소 형식 검증 (정규표현식)
    local ip_regex='^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    
    if ! [[ "$ip" =~ $ip_regex ]]; then
        error_exit "$description IP 주소 형식이 올바르지 않습니다: $ip"
    fi
    
    log "$description IP 주소 형식이 올바릅니다: $ip"
}

# 파일 존재 및 권한 확인
check_file() {
    if [[ ! -f "$NETWORK_CONFIG_FILE" ]]; then
        error_exit "네트워크 설정 파일을 찾을 수 없습니다: $NETWORK_CONFIG_FILE"
    fi
    
    if ! sudo test -r "$NETWORK_CONFIG_FILE"; then
        error_exit "네트워크 설정 파일을 읽을 수 없습니다: $NETWORK_CONFIG_FILE"
    fi
    
    if ! sudo test -w "$NETWORK_CONFIG_FILE"; then
        error_exit "네트워크 설정 파일에 쓰기 권한이 없습니다: $NETWORK_CONFIG_FILE"
    fi
    
    log "네트워크 설정 파일이 존재하고 접근 가능합니다"
}

# IP 주소 검색
search_ip() {
    local search_ip="$1"
    local found_count=0
    
    log "IP 주소 검색 중: $search_ip"
    
    # 정확한 IP 매칭을 위한 패턴 (IP 주소 뒤에 공백, 줄바꿈, / 또는 라인 끝이 와야 함)
    local patterns=(
        "address: $search_ip\$"
        "address: $search_ip/"
        "address:$search_ip\$"
        "address:$search_ip/"
    )
    
    for pattern in "${patterns[@]}"; do
        local count=0
        if sudo grep -q "$pattern" "$NETWORK_CONFIG_FILE" 2>/dev/null; then
            count=$(sudo grep -c "$pattern" "$NETWORK_CONFIG_FILE" 2>/dev/null)
            log "패턴 '$pattern'을 $count개 발견"
            found_count=$((found_count + count))
        fi
    done
    
    echo "$found_count"
}

# IP 주소 교체 실행
replace_ip() {
    local old_ip="$1"
    local new_ip="$2"
    
    log "IP 주소 교체를 시작합니다: $old_ip → $new_ip"
    
    local changes_made=0
    
    # 정확한 IP 매칭으로 교체 (IP 주소 뒤에 공백, 줄바꿈, / 또는 라인 끝이 와야 함)
    
    # address: IP$ (라인 끝) → address: NEW_IP
    if sudo sed -i "s#address: $old_ip\$#address: $new_ip#g" "$NETWORK_CONFIG_FILE" 2>/dev/null; then
        local count=0
        if sudo grep -q "address: $new_ip\$" "$NETWORK_CONFIG_FILE" 2>/dev/null; then
            count=$(sudo grep -c "address: $new_ip\$" "$NETWORK_CONFIG_FILE" 2>/dev/null)
            changes_made=$((changes_made + count))
            log "address 필드(라인 끝)에서 $count개 교체 완료"
        fi
    fi
    
    # address: IP/ → address: NEW_IP/
    if sudo sed -i "s#address: $old_ip/#address: $new_ip/#g" "$NETWORK_CONFIG_FILE" 2>/dev/null; then
        local count=0
        if sudo grep -q "address: $new_ip/" "$NETWORK_CONFIG_FILE" 2>/dev/null; then
            count=$(sudo grep -c "address: $new_ip/" "$NETWORK_CONFIG_FILE" 2>/dev/null)
            changes_made=$((changes_made + count))
            log "address 필드(CIDR 포함)에서 $count개 교체 완료"
        fi
    fi
    
    # address:IP$ (공백 없음, 라인 끝) → address:NEW_IP
    if sudo sed -i "s#address:$old_ip\$#address:$new_ip#g" "$NETWORK_CONFIG_FILE" 2>/dev/null; then
        local count=0
        if sudo grep -q "address:$new_ip\$" "$NETWORK_CONFIG_FILE" 2>/dev/null; then
            count=$(sudo grep -c "address:$new_ip\$" "$NETWORK_CONFIG_FILE" 2>/dev/null)
            changes_made=$((changes_made + count))
            log "address 필드(공백 없음, 라인 끝)에서 $count개 교체 완료"
        fi
    fi
    
    # address:IP/ (공백 없음) → address:NEW_IP/
    if sudo sed -i "s#address:$old_ip/#address:$new_ip/#g" "$NETWORK_CONFIG_FILE" 2>/dev/null; then
        local count=0
        if sudo grep -q "address:$new_ip/" "$NETWORK_CONFIG_FILE" 2>/dev/null; then
            count=$(sudo grep -c "address:$new_ip/" "$NETWORK_CONFIG_FILE" 2>/dev/null)
            changes_made=$((changes_made + count))
            log "address 필드(공백 없음, CIDR 포함)에서 $count개 교체 완료"
        fi
    fi
    
    if [[ $changes_made -gt 0 ]]; then
        success "IP 주소 교체가 완료되었습니다 (총 $changes_made개 항목 변경)"
        return 0
    else
        warn "교체할 IP 주소를 찾지 못했습니다"
        return 1
    fi
}

# 변경 결과 확인
verify_changes() {
    local old_ip="$1"
    local new_ip="$2"
    
    log "변경 결과를 확인합니다..."
    
    # 기존 IP가 남아있는지 정확한 패턴으로 확인
    local remaining_count=0
    local patterns=(
        "address: $old_ip\$"
        "address: $old_ip/"
        "address:$old_ip\$"
        "address:$old_ip/"
    )
    
    for pattern in "${patterns[@]}"; do
        local count=0
        if sudo grep -q "$pattern" "$NETWORK_CONFIG_FILE" 2>/dev/null; then
            count=$(sudo grep -c "$pattern" "$NETWORK_CONFIG_FILE" 2>/dev/null)
            remaining_count=$((remaining_count + count))
        fi
    done
    
    if [[ $remaining_count -gt 0 ]]; then
        warn "일부 기존 IP가 아직 $remaining_count개 위치에 남아있습니다"
        log "남은 기존 IP 위치들:"
        for pattern in "${patterns[@]}"; do
            sudo grep -n "$pattern" "$NETWORK_CONFIG_FILE" 2>/dev/null || true
        done
    else
        success "기존 IP가 모두 제거되었습니다"
    fi
    
    # 새 IP가 제대로 적용되었는지 정확한 패턴으로 확인
    local new_ip_count=0
    local new_patterns=(
        "address: $new_ip\$"
        "address: $new_ip/"
        "address:$new_ip\$"
        "address:$new_ip/"
    )
    
    for pattern in "${new_patterns[@]}"; do
        local count=0
        if sudo grep -q "$pattern" "$NETWORK_CONFIG_FILE" 2>/dev/null; then
            count=$(sudo grep -c "$pattern" "$NETWORK_CONFIG_FILE" 2>/dev/null)
            new_ip_count=$((new_ip_count + count))
        fi
    done
    
    if [[ $new_ip_count -gt 0 ]]; then
        success "새 IP 주소가 $new_ip_count개 위치에 적용되었습니다"
        log "새 IP 적용 위치들:"
        for pattern in "${new_patterns[@]}"; do
            sudo grep -n "$pattern" "$NETWORK_CONFIG_FILE" 2>/dev/null || true
        done
    else
        error "새 IP 주소가 적용되지 않았습니다"
        return 1
    fi
}

# YAML 문법 검증
validate_yaml() {
    if command -v python3 >/dev/null 2>&1; then
        log "YAML 문법을 검증합니다..."
        if sudo python3 -c "import yaml; yaml.safe_load(open('$NETWORK_CONFIG_FILE'))" >/dev/null 2>&1; then
            success "YAML 문법이 올바릅니다"
        else
            error "YAML 문법에 오류가 있습니다"
            return 1
        fi
    else
        warn "Python3이 없어 YAML 문법 검증을 건너뜁니다"
    fi
}

# 메인 함수
main() {
    log "Cloud-init IP 주소 교체 작업을 시작합니다"
    log "기존 IP: $OLD_IP → 새 IP: $NEW_IP"
    
    # 기본 검증 (root 권한 체크는 이미 상단에서 처리됨)
    validate_ip "$OLD_IP" "기존"
    validate_ip "$NEW_IP" "새로운"
    check_file
    
    # IP 검색
    local found_count
    found_count=$(search_ip "$OLD_IP")
    
    if [[ $found_count -eq 0 ]]; then
        warn "지정된 IP 주소를 찾을 수 없습니다: $OLD_IP"
        log "현재 설정 파일 내용:"
        sudo cat "$NETWORK_CONFIG_FILE"
        exit 0
    fi
    
    success "IP 주소를 $found_count개 위치에서 발견했습니다: $OLD_IP"
    
    # IP 교체 실행
    if replace_ip "$OLD_IP" "$NEW_IP"; then
        # 결과 확인
        verify_changes "$OLD_IP" "$NEW_IP"
        
        # YAML 문법 검증
        validate_yaml
        
        echo
        success "모든 작업이 완료되었습니다!"
        echo
        log "cloud-init 설정을 적용하려면 다음 명령어를 실행하세요:"
        echo "  sudo cloud-init clean && sudo cloud-init init --local"
        echo "  또는 시스템 재부팅"
    else
        error_exit "IP 주소 교체에 실패했습니다"
    fi
}

# 스크립트 실행
main "$@"

sudo cloud-init clean -c network
sudo cloud-init init --local
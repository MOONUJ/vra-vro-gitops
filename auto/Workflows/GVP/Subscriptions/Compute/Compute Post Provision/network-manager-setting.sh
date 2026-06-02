#!/bin/bash

# NetworkManager 네트워크 설정 자동 변경 스크립트
# /etc/NetworkManager/system-connections에서 네트워크 설정을 읽어와서
# keepStatic 배열에 있는 IP는 Static으로 유지하고, 나머지는 DHCP로 변경

set -euo pipefail

# 변수 설정
NM_CONNECTIONS_DIR="/etc/NetworkManager/system-connections"
BACKUP_DIR="/etc/NetworkManager/system-connections.backup.$(date +%Y%m%d_%H%M%S)"
keepStatic=(replaceKeepStatic)  # Static으로 유지할 IP 주소 목록 (이 배열에 없는 인터페이스들은 DHCP로 변경)

# 로그 함수
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# 에러 처리 함수
error_exit() {
    echo "ERROR: $1" >&2
    exit 1
}

# root 권한 확인
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error_exit "이 스크립트는 root 권한으로 실행해야 합니다."
    fi
}

# NetworkManager 서비스 확인
check_networkmanager() {
    if ! systemctl is-active --quiet NetworkManager; then
        error_exit "NetworkManager 서비스가 실행되고 있지 않습니다."
    fi
    
    if [[ ! -d "$NM_CONNECTIONS_DIR" ]]; then
        error_exit "NetworkManager 연결 디렉토리를 찾을 수 없습니다: $NM_CONNECTIONS_DIR"
    fi
}

# 백업 생성
create_backup() {
    log "설정 파일들을 백업합니다: $BACKUP_DIR"
    cp -r "$NM_CONNECTIONS_DIR" "$BACKUP_DIR"
    log "백업 완료: $BACKUP_DIR"
}

# NetworkManager 연결 프로파일에서 IP 주소 추출
get_ip_from_profile() {
    local profile_file="$1"
    local ip_addresses=()
    
    log "    프로파일 파싱: $(basename "$profile_file")"
    
    # [ipv4] 섹션 내에서만 method와 address 추출
    local in_ipv4_section=false
    local ipv4_method=""
    local ipv4_addresses=()
    
    while IFS= read -r line; do
        # 빈 라인이나 주석 건너뛰기
        [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
        
        # 섹션 감지
        if [[ "$line" =~ ^\[([^\]]+)\]$ ]]; then
            local section="${BASH_REMATCH[1]}"
            if [[ "$section" == "ipv4" ]]; then
                in_ipv4_section=true
                log "    [ipv4] 섹션 진입"
            else
                in_ipv4_section=false
            fi
            continue
        fi
        
        # ipv4 섹션 내에서만 처리
        if [[ "$in_ipv4_section" == "true" ]]; then
            if [[ "$line" =~ ^method=(.+)$ ]]; then
                ipv4_method="${BASH_REMATCH[1]}"
                log "    IPv4 method: $ipv4_method"
            elif [[ "$line" =~ ^address[0-9]+=(.+)$ ]]; then
                local addr="${BASH_REMATCH[1]}"
                addr=$(echo "$addr" | xargs)  # 공백 제거
                if [[ "$addr" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+(/[0-9]+)?$ ]]; then
                    ipv4_addresses+=("$addr")
                    log "    IPv4 주소 발견: $addr"
                fi
            fi
        fi
    done < "$profile_file"
    
    # IPv4가 manual 방식이고 주소가 있는 경우만 반환
    if [[ "$ipv4_method" == "manual" && ${#ipv4_addresses[@]} -gt 0 ]]; then
        log "    IPv4 static 설정 확인됨"
        ip_addresses=("${ipv4_addresses[@]}")
    else
        log "    IPv4 static 설정 없음 (method=$ipv4_method, 주소 개수=${#ipv4_addresses[@]})"
    fi
    
    log "    최종 추출된 IP 개수: ${#ip_addresses[@]}"
    
    printf '%s\n' "${ip_addresses[@]}"
}

# IP 주소가 keepStatic 배열에 있는지 확인 (Static으로 유지할 IP인지 확인)
is_ip_keep_static() {
    local target_ip="$1"
    
    # 빈 IP 주소는 확인하지 않음
    [[ -z "$target_ip" ]] && return 1
    
    # NetworkManager 설정에서 CIDR 표기법에서 IP 주소만 추출 (예: 192.168.1.100/24 -> 192.168.1.100)
    local clean_target_ip="${target_ip%%/*}"
    
    # keepStatic 배열에서 해당 IP 찾기 (keepStatic은 단순 IP 주소만 포함)
    for keep_ip in "${keepStatic[@]}"; do
        if [[ "$keep_ip" == "$clean_target_ip" ]]; then
            log "    IP 매치: $clean_target_ip (설정파일: $target_ip, keepStatic: $keep_ip)"
            return 0  # 찾음 (Static으로 유지)
        fi
    done
    
    return 1  # 찾지 못함 (DHCP로 변경)
}

# NetworkManager 연결 프로파일을 DHCP로 변경
convert_to_dhcp() {
    local profile_file="$1"
    local profile_name="$2"
    local temp_file="${profile_file}.tmp"
    
    log "DHCP로 변경 중: $profile_name"
    
    # 임시 파일 생성
    : > "$temp_file"
    
    local in_ipv4_section=false
    local in_ipv6_section=false
    local skip_multiline=false
    
    while IFS= read -r line || [[ -n "$line" ]]; do
        # 빈 라인 처리
        if [[ -z "$line" || "$line" =~ ^[[:space:]]*$ ]]; then
            echo "$line" >> "$temp_file"
            continue
        fi
        
        # 섹션 감지
        if [[ "$line" =~ ^\[.*\]$ ]]; then
            skip_multiline=false
            if [[ "$line" =~ ^\[ipv4\]$ ]]; then
                in_ipv4_section=true
                in_ipv6_section=false
            elif [[ "$line" =~ ^\[ipv6\]$ ]]; then
                in_ipv4_section=false
                in_ipv6_section=true
            else
                in_ipv4_section=false
                in_ipv6_section=false
            fi
            echo "$line" >> "$temp_file"
            continue
        fi
        
        # 멀티라인 속성 건너뛰기 (addresses가 여러 줄에 걸쳐있는 경우)
        if [[ "$skip_multiline" == "true" ]]; then
            # 다음 속성이 시작될 때까지 건너뛰기 (key=value 형태가 나올 때까지)
            if [[ "$line" =~ ^[a-zA-Z0-9_-]+= ]]; then
                skip_multiline=false
            else
                continue  # 현재 줄 건너뛰기
            fi
        fi
        
        # ipv4 섹션 내에서 처리
        if [[ "$in_ipv4_section" == "true" ]]; then
            case "$line" in
                method=*)
                    echo "method=auto" >> "$temp_file"
                    ;;
                address[0-9]*=*|gateway=*|dns=*|dns-search=*|dns-options=*|dns-priority=*)
                    # 모든 address 관련 설정들 및 DNS/게이트웨이 설정 제거
                    ;;
                route[0-9]*=*)
                    # 정적 라우트 제거
                    ;;
                may-fail=*|route-metric=*|dhcp-timeout=*|dad-timeout=*)
                    # DHCP에서도 유효한 설정들 유지
                    echo "$line" >> "$temp_file"
                    ;;
                ignore-auto-dns=*|ignore-auto-routes=*)
                    # 자동 설정 무시 옵션들 제거 (DHCP에서는 필요없음)
                    ;;
                *)
                    # 기타 설정들은 유지
                    echo "$line" >> "$temp_file"
                    ;;
            esac
        else
            # ipv4 섹션이 아닌 경우 그대로 복사
            echo "$line" >> "$temp_file"
        fi
    done < "$profile_file"
    
    # ipv4 섹션이 없는 경우 추가
    if ! grep -q "^\[ipv4\]" "$temp_file"; then
        cat >> "$temp_file" << EOF

[ipv4]
method=auto
EOF
    fi
    
    # 원본 파일 교체
    mv "$temp_file" "$profile_file"
    
    # 권한 설정 (NetworkManager 연결 파일은 600)
    chmod 600 "$profile_file"
}

# 연결 프로파일 처리
process_connection_profiles() {
    local processed_count=0
    local dhcp_changed_count=0
    local static_kept_count=0
    
    # NetworkManager 연결 파일들 처리
    for profile_file in "$NM_CONNECTIONS_DIR"/*.nmconnection; do
        [[ ! -f "$profile_file" ]] && continue
        
        local profile_name=$(basename "$profile_file" .nmconnection)
        processed_count=$((processed_count + 1))
        
        log "처리 중인 프로파일: $profile_name"
        
        # interface-name 값을 추출하여 id 값을 동일하게 변경
        local interface_name=$(awk -F= '/^interface-name=/ {print $2}' "$profile_file")
        if [[ -n "$interface_name" ]]; then
            sed -i "s/^id=.*/id=$interface_name/" "$profile_file"
            log "  프로파일 ID를 interface-name ($interface_name)과 동일하게 변경함"
        fi
        
        # 연결 프로파일에서 IP 주소들 추출
        readarray -t ip_addresses < <(get_ip_from_profile "$profile_file")
        
        if [[ ${#ip_addresses[@]} -eq 0 ]]; then
            log "  IP 주소를 찾을 수 없습니다. (이미 DHCP이거나 설정 없음)"
            continue
        fi
        
        # IP 주소들 중 하나라도 keepStatic에 있는지 확인
        local keep_static=false
        local matched_ip=""
        for ip_addr in "${ip_addresses[@]}"; do
            if is_ip_keep_static "$ip_addr"; then
                keep_static=true
                matched_ip="$ip_addr"
                break
            fi
        done
        
        if [[ "$keep_static" == "true" ]]; then
            log "  Static 유지: $matched_ip (keepStatic 목록에 있음)"
            static_kept_count=$((static_kept_count + 1))
        else
            log "  DHCP로 변경: ${ip_addresses[*]} (keepStatic 목록에 없음)"
            convert_to_dhcp "$profile_file" "$profile_name"
            dhcp_changed_count=$((dhcp_changed_count + 1))
        fi
    done
    
    log "처리 완료: 총 $processed_count개 프로파일 (Static 유지: $static_kept_count개, DHCP 변경: $dhcp_changed_count개)"
}

# NetworkManager 재로드
reload_networkmanager() {
    log "NetworkManager 설정을 재로드합니다..."
    
    # 연결 재로드
    if nmcli connection reload; then
        log "연결 재로드 완료"
    else
        log "WARNING: 연결 재로드 실패"
    fi
}

# 설정 확인
verify_configuration() {
    log "현재 네트워크 설정을 확인합니다..."
    
    echo
    echo "=== 현재 IP 설정 ==="
    ip addr show | grep -E "^\d|inet " | grep -v "127.0.0.1" | head -20
    
    echo
    echo "=== 변경된 설정 파일들 ==="
    for profile_file in "$NM_CONNECTIONS_DIR"/*.nmconnection; do
        [[ ! -f "$profile_file" ]] && continue
        
        local profile_name=$(basename "$profile_file" .nmconnection)
        local method=$(grep "^method=" "$profile_file" 2>/dev/null | cut -d'=' -f2 || echo "unknown")
        local address1=$(grep "^address1=" "$profile_file" 2>/dev/null | cut -d'=' -f2 || echo "none")
        
        echo "  $profile_name: method=$method, address1=$address1"
    done
}

# 메인 함수
main() {
    log "NetworkManager 네트워크 설정 변경을 시작합니다..."
    
    # keepStatic 배열 예시 (Static으로 유지할 IP 주소 목록)
    # keepStatic=("192.168.1.100" "10.0.1.50" "172.16.0.10")
    
    if [[ ${#keepStatic[@]} -gt 0 ]]; then
        log "Static으로 유지할 IP 주소 목록: ${keepStatic[*]}"
        log "이 목록에 없는 연결들은 모두 DHCP로 변경됩니다."
    else
        log "Static으로 유지할 IP 주소가 지정되지 않았습니다. 모든 연결이 DHCP로 변경됩니다."
    fi
    
    check_root
    check_networkmanager
    create_backup
    
    # 연결 프로파일 처리
    process_connection_profiles
    
    # NetworkManager 재로드
    reload_networkmanager
    
    # 설정 확인
    verify_configuration
    
    log "NetworkManager 네트워크 설정 변경이 완료되었습니다."
    log "백업 디렉토리: $BACKUP_DIR"
    echo
    echo "문제가 발생한 경우 다음 명령으로 복구할 수 있습니다:"
    echo "  sudo rm -rf $NM_CONNECTIONS_DIR/*"
    echo "  sudo cp $BACKUP_DIR/* $NM_CONNECTIONS_DIR/"
    echo "  sudo chmod 600 $NM_CONNECTIONS_DIR/*"
    echo "  sudo systemctl restart NetworkManager"
}

# 스크립트 실행
main "$@"
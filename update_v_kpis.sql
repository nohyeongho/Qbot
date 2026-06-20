DROP VIEW IF EXISTS v_kpis;

CREATE VIEW v_kpis AS
SELECT
  -- 전체 사용자 수 (NULL 방지)
  COUNT(DISTINCT COALESCE("userName", '알수없음') || '(' || COALESCE("userNo", '알수없음') || ')') AS total_users,
  
  -- 총 검색건수
  COUNT(CASE WHEN "userAction" = 'QUESTION' THEN id END) AS total_inquiries,

  -- 해결 건수
  COUNT(CASE WHEN "userAction" = 'QUESTION' AND "aiResultStatus" = 'SUCCESS' THEN id END) AS resolved_count,

  -- 전체 활성 일수
  COUNT(DISTINCT CASE WHEN "userAction" = 'QUESTION' THEN "chatDate" END) AS active_days,

  -- 평일 일평균 사용자 계산을 위한 일자별 사번 기준 접속자 총합 (주말 및 주요 공휴일 제외)
  -- 2026년 주요 공휴일 및 대체공휴일을 하드코딩으로 제외합니다.
  COUNT(DISTINCT CASE 
    WHEN EXTRACT(ISODOW FROM "chatDate") < 6 
    AND TO_CHAR("chatDate", 'MM-DD') NOT IN ('01-01', '02-16', '02-17', '02-18', '03-02', '05-01', '05-05', '05-25', '06-03', '07-17', '08-17', '09-24', '09-25', '10-05', '10-09', '12-25') 
    THEN "userNo" || '_' || TO_CHAR("chatDate", 'YYYY-MM-DD') 
  END) AS sum_daily_users_wd,
  
  -- 평일 기준 총 검색건수 (주말 및 공휴일 제외)
  COUNT(CASE 
    WHEN "userAction" = 'QUESTION' 
    AND EXTRACT(ISODOW FROM "chatDate") < 6 
    AND TO_CHAR("chatDate", 'MM-DD') NOT IN ('01-01', '02-16', '02-17', '02-18', '03-02', '05-01', '05-05', '05-25', '06-03', '07-17', '08-17', '09-24', '09-25', '10-05', '10-09', '12-25') 
    THEN id 
  END) AS total_inquiries_wd,
  
  -- 평일 기준 활성 일수 (주말 및 공휴일 제외)
  COUNT(DISTINCT CASE 
    WHEN "userAction" = 'QUESTION' 
    AND EXTRACT(ISODOW FROM "chatDate") < 6 
    AND TO_CHAR("chatDate", 'MM-DD') NOT IN ('01-01', '02-16', '02-17', '02-18', '03-02', '05-01', '05-05', '05-25', '06-03', '07-17', '08-17', '09-24', '09-25', '10-05', '10-09', '12-25') 
    THEN "chatDate" 
  END) AS active_days_wd
FROM chat_logs;

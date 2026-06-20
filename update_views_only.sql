-- =====================================================================
-- 뷰(View)만 업데이트하는 안전한 스크립트
-- 주의: 이 파일만 Supabase SQL Editor에서 실행하세요.
--      테이블(chat_logs)이나 데이터는 건드리지 않습니다.
-- =====================================================================

-- 기존 뷰 삭제 (뷰만 삭제, 테이블/데이터는 유지)
DROP VIEW IF EXISTS v_kpis;
DROP VIEW IF EXISTS v_hourly;
DROP VIEW IF EXISTS v_types;
DROP VIEW IF EXISTS v_top_users;
DROP VIEW IF EXISTS v_top_centers;

-- KPI 뷰
CREATE VIEW v_kpis AS
SELECT
  COUNT(DISTINCT COALESCE("userName", '알수없음') || '(' || COALESCE("userNo", '알수없음') || ')') AS total_users,
  COUNT(CASE WHEN "userAction" = 'QUESTION' THEN id END) AS total_inquiries,
  COUNT(CASE WHEN "userAction" = 'QUESTION' AND "aiResultStatus" = 'SUCCESS' THEN id END) AS resolved_count,
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

-- 시간대별 차트 뷰
CREATE VIEW v_hourly AS
SELECT
  "chatHour" AS chat_hour,
  COUNT(id) AS inquiry_count
FROM chat_logs
WHERE "userAction" = 'QUESTION'
GROUP BY "chatHour";

-- 문의 유형 차트 뷰
CREATE VIEW v_types AS
SELECT
  "questionTypeCd" AS question_type,
  COUNT(id) AS type_count
FROM chat_logs
WHERE "userAction" = 'QUESTION'
GROUP BY "questionTypeCd";

-- 상위 사용자 10명 뷰
CREATE VIEW v_top_users AS
SELECT
  "userName" AS user_name,
  "userNo" AS user_no,
  COUNT(id) AS inquiry_count
FROM chat_logs
WHERE "userAction" = 'QUESTION'
GROUP BY "userName", "userNo"
ORDER BY COUNT(id) DESC
LIMIT 10;

-- 모든 센터의 일별 활동 산점도용 뷰 (전체 센터)
DROP VIEW IF EXISTS v_top_centers;
CREATE VIEW v_top_centers AS
SELECT
  "userDeptName" AS user_dept_name,
  "chatDate" AS chat_date,
  COUNT(DISTINCT "userNo") AS user_count,
  COUNT(id) AS inquiry_count
FROM chat_logs
WHERE "userAction" = 'QUESTION' AND "userDeptName" IS NOT NULL
GROUP BY "userDeptName", "chatDate"
ORDER BY "userDeptName", "chatDate";

-- 일별 사용자 및 검색건수 뷰
DROP VIEW IF EXISTS v_daily;
CREATE VIEW v_daily AS
SELECT
  "chatDate" AS chat_date,
  COUNT(DISTINCT "userNo") AS user_count,
  COUNT(CASE WHEN "userAction" = 'QUESTION' THEN id END) AS inquiry_count
FROM chat_logs
GROUP BY "chatDate"
ORDER BY "chatDate";

-- 자주 묻는 질문(FAQ) 및 Top 키워드 뷰
DROP VIEW IF EXISTS v_faq;
CREATE VIEW v_faq AS
SELECT
  "chatMsg" AS chat_msg,
  COUNT(id) AS inquiry_count
FROM chat_logs
WHERE "userAction" = 'QUESTION' AND "chatMsg" IS NOT NULL AND "chatMsg" != ''
GROUP BY "chatMsg"
ORDER BY COUNT(id) DESC
LIMIT 50;

-- 제품별 현황 뷰
DROP VIEW IF EXISTS v_products;
CREATE VIEW v_products AS
SELECT
  "prodLvl2Name" AS prod_name,
  "questionTypeCd" AS question_type,
  COUNT(id) AS inquiry_count
FROM chat_logs
WHERE "userAction" = 'QUESTION' AND "prodLvl2Name" IS NOT NULL AND "prodLvl2Name" != ''
GROUP BY "prodLvl2Name", "questionTypeCd";

-- 사용자 피드백(좋아요/싫어요) 뷰
DROP VIEW IF EXISTS v_feedback;
CREATE VIEW v_feedback AS
SELECT
  CASE 
    WHEN "userActionValue" LIKE '%"GOOD"%' THEN 'GOOD'
    WHEN "userActionValue" LIKE '%"BAD"%' THEN 'BAD'
    ELSE 'OTHER'
  END AS feedback_type,
  COUNT(id) AS feedback_count
FROM chat_logs
WHERE "userAction" = 'GOOD_BAD_CLICK'
GROUP BY 
  CASE 
    WHEN "userActionValue" LIKE '%"GOOD"%' THEN 'GOOD'
    WHEN "userActionValue" LIKE '%"BAD"%' THEN 'BAD'
    ELSE 'OTHER'
  END;

-- 일별 제품 현황 뷰 (제품군별 필터링용)
DROP VIEW IF EXISTS v_prod_daily;
CREATE VIEW v_prod_daily AS
SELECT
  "chatDate" AS chat_date,
  "prodLvl2Name" AS prod_name,
  COUNT(id) AS inquiry_count
FROM chat_logs
WHERE "userAction" = 'QUESTION' AND "prodLvl2Name" IS NOT NULL AND "prodLvl2Name" != ''
GROUP BY "chatDate", "prodLvl2Name"
ORDER BY "chatDate";

-- 탑 모델 현황 뷰 (하단 모델명 순위 테이블용)
DROP VIEW IF EXISTS v_top_models;
CREATE VIEW v_top_models AS
SELECT
  "prodLvl3Name" AS model_name,
  MAX("prodLvl2Name") AS prod_name,
  MAX("questionTypeCd") AS question_type,
  MAX("chatDate") AS last_chat_date,
  COUNT(id) AS inquiry_count,
  COUNT(CASE WHEN "aiResultStatus" = 'SUCCESS' THEN id END) AS success_count
FROM chat_logs
WHERE "userAction" = 'QUESTION' AND "prodLvl3Name" IS NOT NULL AND "prodLvl3Name" != ''
GROUP BY "prodLvl3Name"
ORDER BY COUNT(id) DESC
LIMIT 50;

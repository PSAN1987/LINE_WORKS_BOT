FORM_HTML = r"""
<!DOCTYPE html>
<html>
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
  <style>
    body {
      margin: 16px;
      font-family: sans-serif;
      font-size: 16px;
      line-height: 1.5;
    }
    h1 {
      margin-bottom: 24px;
      font-size: 1.2em;
    }
    form {
      max-width: 600px;
      margin: 0 auto;
    }
    /* ▼▼ ここに input[type="file"] を追加 ▼▼ */
    input[type="text"],
    input[type="number"],
    input[type="email"],
    input[type="date"],
    select,
    button,
    input[type="file"] {
      display: block;
      width: 100%;
      box-sizing: border-box;
      margin-bottom: 16px;
      padding: 8px;
      font-size: 16px;
    }
    .radio-group,
    .checkbox-group {
      margin-bottom: 16px;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .radio-group label,
    .checkbox-group label {
      display: flex;
      align-items: center;
    }
    h3 {
      margin-top: 24px;
      margin-bottom: 8px;
      font-size: 1.1em;
    }
    p.instruction {
      font-size: 14px;
      color: #555;
    }
    .tshirt-container {
      width: 300px;
      margin-bottom: 16px;
      position: relative;
    }
    svg {
      width: 100%;
      height: auto;
      display: block;
    }
    .tshirt-shape {
      fill: #f5f5f5;
      stroke: #aaa;
      stroke-width: 2;
    }
    .click-area {
      fill: white;
      stroke: black;
      cursor: pointer;
      transition: 0.2s;
    }
    .click-area:hover {
      fill: orange;
    }
    .click-area.selected {
      fill: orange;
    }
    .area-label {
      pointer-events: none;
      font-size: 12px;
      text-anchor: middle;
      alignment-baseline: middle;
      user-select: none;
    }
  </style>
</head>
<body>
  <h1>WEBフォームから注文</h1>
  <form action="/webform_submit" method="POST" enctype="multipart/form-data">
    <input type="hidden" name="user_id" value="{{ user_id }}" />

    <label>申込日:</label>
    <input type="date" name="application_date" value="{{ extracted_data['application_date'] or '' }}">

    <label>配達日:</label>
    <input type="date" name="delivery_date" value="{{ extracted_data['delivery_date'] or '' }}">

    <label>使用日:</label>
    <input type="date" name="use_date" value="{{ extracted_data['use_date'] or '' }}">

    <label>利用する学割特典:</label>
    <select name="discount_option">
      <option value="早割" {% if extracted_data['discount_option'] == '早割' %}selected{% endif %}>早割</option>
      <option value="タダ割" {% if extracted_data['discount_option'] == 'タダ割' %}selected{% endif %}>タダ割</option>
      <option value="いっしょ割り" {% if extracted_data['discount_option'] == 'いっしょ割り' %}selected{% endif %}>いっしょ割り</option>
    </select>

    <label>学校名:</label>
    <input type="text" name="school_name" value="{{ extracted_data['school_name'] or '' }}">

    <label>LINEアカウント名:</label>
    <input type="text" name="line_account" value="{{ extracted_data['line_account'] or '' }}">

    <label>団体名:</label>
    <input type="text" name="group_name" value="{{ extracted_data['group_name'] or '' }}">

    <label>学校住所:</label>
    <input type="text" name="school_address" value="{{ extracted_data['school_address'] or '' }}">

    <label>学校TEL:</label>
    <input type="text" name="school_tel" value="{{ extracted_data['school_tel'] or '' }}">

    <label>担任名:</label>
    <input type="text" name="teacher_name" value="{{ extracted_data['teacher_name'] or '' }}">

    <label>担任携帯:</label>
    <input type="text" name="teacher_tel" value="{{ extracted_data['teacher_tel'] or '' }}">

    <label>担任メール:</label>
    <input type="email" name="teacher_email" value="{{ extracted_data['teacher_email'] or '' }}">

    <label>代表者:</label>
    <input type="text" name="representative" value="{{ extracted_data['representative'] or '' }}">

    <label>代表者TEL:</label>
    <input type="text" name="rep_tel" value="{{ extracted_data['rep_tel'] or '' }}">

    <label>代表者メール:</label>
    <input type="email" name="rep_email" value="{{ extracted_data['rep_email'] or '' }}">

    <!-- ▼▼ ここから「お届け先」追加 ▼▼ -->
    <label>お届け先 郵便番号:</label>
    <input type="text" id="delivery_zip" placeholder="例: 1000001" value="{{ extracted_data['delivery_zip'] or '' }}">
    <button type="button" onclick="fetchAddress()">住所を自動入力</button>
    <div>※半角数字で入力、ハイフン不要</div>

    <label>お届け先住所:</label>
    <input type="text" id="delivery_address" name="delivery_address" placeholder="都道府県～町域まで自動入力" value="{{ extracted_data['delivery_address'] or '' }}">

    <label>建物・部屋番号 (任意):</label>
    <input type="text" id="delivery_address2" name="delivery_address2" placeholder="建物名など" value="{{ extracted_data['delivery_address2'] or '' }}">
    <!-- ▼▼ 「お届け先」ここまで ▼▼ -->


    <label>デザイン確認方法:</label>
    <select name="design_confirm">
      <option value="LINE代表者" {% if extracted_data['design_confirm'] == 'LINE代表者' %}selected{% endif %}>LINE代表者</option>
      <option value="LINEご担任(保護者)" {% if extracted_data['design_confirm'] == 'LINEご担任(保護者)' %}selected{% endif %}>LINEご担任(保護者)</option>
      <option value="メール代表者" {% if extracted_data['design_confirm'] == 'メール代表者' %}selected{% endif %}>メール代表者</option>
      <option value="メールご担任(保護者)" {% if extracted_data['design_confirm'] == 'メールご担任(保護者)' %}selected{% endif %}>メールご担任(保護者)</option>
    </select>

    <label>お支払い方法:</label>
    <select name="payment_method">
      <option value="代金引換(ヤマト運輸/現金のみ)" {% if extracted_data['payment_method'] == '代金引換(ヤマト運輸/現金のみ)' %}selected{% endif %}>代金引換(ヤマト運輸/現金のみ)</option>
      <option value="背中払い(コンビニ/郵便振替)" {% if extracted_data['payment_method'] == '背中払い(コンビニ/郵便振替)' %}selected{% endif %}>背中払い(コンビニ/郵便振替)</option>
      <option value="背中払い(銀行振込)" {% if extracted_data['payment_method'] == '背中払い(銀行振込)' %}selected{% endif %}>背中払い(銀行振込)</option>
      <option value="先払い(銀行振込)" {% if extracted_data['payment_method'] == '先払い(銀行振込)' %}selected{% endif %}>先払い(銀行振込)</option>
    </select>

    <label>商品名:</label>
    <select name="product_name">
      <option value="ドライTシャツ" {% if extracted_data['product_name'] == 'ドライTシャツ' %}selected{% endif %}>ドライTシャツ</option>
      <option value="ヘビーウェイトTシャツ" {% if extracted_data['product_name'] == 'ヘビーウェイトTシャツ' %}selected{% endif %}>ヘビーウェイトTシャツ</option>
      <option value="ドライポロシャツ" {% if extracted_data['product_name'] == 'ドライポロシャツ' %}selected{% endif %}>ドライポロシャツ</option>
      <option value="ドライメッシュビブス" {% if extracted_data['product_name'] == 'ドライメッシュビブス' %}selected{% endif %}>ドライメッシュビブス</option>
      <option value="ドライベースボールシャツ" {% if extracted_data['product_name'] == 'ドライベースボールシャツ' %}selected{% endif %}>ドライベースボールシャツ</option>
      <option value="ドライロングスリープTシャツ" {% if extracted_data['product_name'] == 'ドライロングスリープTシャツ' %}selected{% endif %}>ドライロングスリープTシャツ</option>
      <option value="ドライハーフパンツ" {% if extracted_data['product_name'] == 'ドライハーフパンツ' %}selected{% endif %}>ドライハーフパンツ</option>
      <option value="ヘビーウェイトロングスリープTシャツ" {% if extracted_data['product_name'] == 'ヘビーウェイトロングスリープTシャツ' %}selected{% endif %}>ヘビーウェイトロングスリープTシャツ</option>
      <option value="クルーネックライトトレーナー" {% if extracted_data['product_name'] == 'クルーネックライトトレーナー' %}selected{% endif %}>クルーネックライトトレーナー</option>
      <option value="フーデッドライトパーカー" {% if extracted_data['product_name'] == 'フーデッドライトパーカー' %}selected{% endif %}>フーデッドライトパーカー</option>
      <option value="スタンダードトレーナー" {% if extracted_data['product_name'] == 'スタンダードトレーナー' %}selected{% endif %}>スタンダードトレーナー</option>
      <option value="スタンダードWフードパーカー" {% if extracted_data['product_name'] == 'スタンダードWフードパーカー' %}selected{% endif %}>スタンダードWフードパーカー</option>
      <option value="ジップアップライトパーカー" {% if extracted_data['product_name'] == 'ジップアップライトパーカー' %}selected{% endif %}>ジップアップライトパーカー</option>
    </select>

    <label>商品カラー:</label>
    <input type="text" name="product_color" value="{{ extracted_data['product_color'] or '' }}">

    <label>サイズ(SS):</label>
    <input type="number" name="size_ss" value="{{ extracted_data['size_ss'] or '' }}">
    <label>サイズ(S):</label>
    <input type="number" name="size_s" value="{{ extracted_data['size_s'] or '' }}">
    <label>サイズ(M):</label>
    <input type="number" name="size_m" value="{{ extracted_data['size_m'] or '' }}">
    <label>サイズ(L):</label>
    <input type="number" name="size_l" value="{{ extracted_data['size_l'] or '' }}">
    <label>サイズ(LL):</label>
    <input type="number" name="size_ll" value="{{ extracted_data['size_ll'] or '' }}">
    <label>サイズ(LLL):</label>
    <input type="number" name="size_lll" value="{{ extracted_data['size_lll'] or '' }}">


    <!-- ▼▼ 前面プリント ▼▼ -->
    <h3>プリント位置: 前</h3>
    <div class="radio-group">
      <label>
        <input type="radio" name="print_size_front" value="おまかせ (最大:横28cm x 縦35cm以内)"
          {% if extracted_data['print_size_front'] == "おまかせ (最大:横28cm x 縦35cm以内)" or not extracted_data['print_size_front'] or extracted_data['print_size_front'] == "おまかせ (最大:横28cm x 縦35cm以内)" %}
            checked
          {% endif %}>
        おまかせ (最大:横28cm x 縦35cm以内)
      </label>
      <label>
        <input type="radio" name="print_size_front" value="custom"
          {% if extracted_data['print_size_front'] == "custom" %}checked{% endif %}>
        ヨコcm x タテcmくらい(入力する):
      </label>
    </div>
    <input type="text" name="print_size_front_custom"
           placeholder="例: 20cm x 15cm"
           value="{{ extracted_data['print_size_front_custom'] or '' }}">

    <!-- ▼▼ プリントカラー(前) - シンプルな選択式 (複数選択) ▼▼ -->
    <label>プリントカラー(前):</label>
    <select name="print_color_front[]" multiple onchange="limitSelection(this, 4)">
      <option value="" {% if not extracted_data['print_color_front'] %}selected{% endif %}>選択してください</option>
      {% set front_colors = extracted_data['print_color_front'] if extracted_data['print_color_front'] else [] %}
      <option value="ホワイト" {% if 'ホワイト' in front_colors %}selected{% endif %}>ホワイト</option>
      <option value="ライトグレー" {% if 'ライトグレー' in front_colors %}selected{% endif %}>ライトグレー</option>
      <option value="ダークグレー" {% if 'ダークグレー' in front_colors %}selected{% endif %}>ダークグレー</option>
      <option value="ブラック" {% if 'ブラック' in front_colors %}selected{% endif %}>ブラック</option>
      <option value="サックス" {% if 'サックス' in front_colors %}selected{% endif %}>サックス</option>
      <option value="ブルー" {% if 'ブルー' in front_colors %}selected{% endif %}>ブルー</option>
      <option value="ネイビー" {% if 'ネイビー' in front_colors %}selected{% endif %}>ネイビー</option>
      <option value="ライトピンク" {% if 'ライトピンク' in front_colors %}selected{% endif %}>ライトピンク</option>
      <option value="ローズピンク" {% if 'ローズピンク' in front_colors %}selected{% endif %}>ローズピンク</option>
      <option value="ホットピンク" {% if 'ホットピンク' in front_colors %}selected{% endif %}>ホットピンク</option>
      <option value="レッド" {% if 'レッド' in front_colors %}selected{% endif %}>レッド</option>
      <option value="ワインレッド" {% if 'ワインレッド' in front_colors %}selected{% endif %}>ワインレッド</option>
      <option value="ミントグリーン" {% if 'ミントグリーン' in front_colors %}selected{% endif %}>ミントグリーン</option>
      <option value="エメラルドグリーン" {% if 'エメラルドグリーン' in front_colors %}selected{% endif %}>エメラルドグリーン</option>
      <option value="パステルイエロー" {% if 'パステルイエロー' in front_colors %}selected{% endif %}>パステルイエロー</option>
      <option value="イエロー" {% if 'イエロー' in front_colors %}selected{% endif %}>イエロー</option>
      <option value="ゴールドイエロー" {% if 'ゴールドイエロー' in front_colors %}selected{% endif %}>ゴールドイエロー</option>
      <option value="オレンジ" {% if 'オレンジ' in front_colors %}selected{% endif %}>オレンジ</option>
      <option value="イエローグリーン" {% if 'イエローグリーン' in front_colors %}selected{% endif %}>イエローグリーン</option>
      <option value="グリーン" {% if 'グリーン' in front_colors %}selected{% endif %}>グリーン</option>
      <option value="ダークグリーン" {% if 'ダークグリーン' in front_colors %}selected{% endif %}>ダークグリーン</option>
      <option value="ライトパープル" {% if 'ライトパープル' in front_colors %}selected{% endif %}>ライトパープル</option>
      <option value="パープル" {% if 'パープル' in front_colors %}selected{% endif %}>パープル</option>
      <option value="クリーム" {% if 'クリーム' in front_colors %}selected{% endif %}>クリーム</option>
      <option value="ライトブラウン" {% if 'ライトブラウン' in front_colors %}selected{% endif %}>ライトブラウン</option>
      <option value="ダークブラウン" {% if 'ダークブラウン' in front_colors %}selected{% endif %}>ダークブラウン</option>
      <option value="シルバー" {% if 'シルバー' in front_colors %}selected{% endif %}>シルバー</option>
      <option value="ゴールド" {% if 'ゴールド' in front_colors %}selected{% endif %}>ゴールド</option>
      <option value="グリッターシルバー" {% if 'グリッターシルバー' in front_colors %}selected{% endif %}>グリッターシルバー</option>
      <option value="グリッターゴールド" {% if 'グリッターゴールド' in front_colors %}selected{% endif %}>グリッターゴールド</option>
      <option value="グリッターブラック" {% if 'グリッターブラック' in front_colors %}selected{% endif %}>グリッターブラック</option>
      <option value="グリッターイエロー" {% if 'グリッターイエロー' in front_colors %}selected{% endif %}>グリッターイエロー</option>
      <option value="グリッターピンク" {% if 'グリッターピンク' in front_colors %}selected{% endif %}>グリッターピンク</option>
      <option value="グリッターレッド" {% if 'グリッターレッド' in front_colors %}selected{% endif %}>グリッターレッド</option>
      <option value="グリッターグリーン" {% if 'グリッターグリーン' in front_colors %}selected{% endif %}>グリッターグリーン</option>
      <option value="グリッターブルー" {% if 'グリッターブルー' in front_colors %}selected{% endif %}>グリッターブルー</option>
      <option value="グリッターパープル" {% if 'グリッターパープル' in front_colors %}selected{% endif %}>グリッターパープル</option>
      <option value="蛍光オレンジ" {% if '蛍光オレンジ' in front_colors %}selected{% endif %}>蛍光オレンジ</option>
      <option value="蛍光ピンク" {% if '蛍光ピンク' in front_colors %}selected{% endif %}>蛍光ピンク</option>
      <option value="蛍光グリーン" {% if '蛍光グリーン' in front_colors %}selected{% endif %}>蛍光グリーン</option>
      <option value="フルカラー(小)" {% if 'フルカラー(小)' in front_colors %}selected{% endif %}>フルカラー(小)</option>
      <option value="フルカラー(中)" {% if 'フルカラー(中)' in front_colors %}selected{% endif %}>フルカラー(中)</option>
      <option value="フルカラー(大)" {% if 'フルカラー(大)' in front_colors %}selected{% endif %}>フルカラー(大)</option>
    </select>

    <label>フォントNo.(前):</label>
    <select name="font_no_front">
      <option value="" {% if not extracted_data['font_no_front'] %}selected{% endif %}>選択してください</option>
      {% set f_front = extracted_data['font_no_front'] %}
      <option value="E-01" {% if f_front == 'E-01' %}selected{% endif %}>E-01</option>
      <option value="E-02" {% if f_front == 'E-02' %}selected{% endif %}>E-02</option>
      <option value="E-03" {% if f_front == 'E-03' %}selected{% endif %}>E-03</option>
      <option value="E-05" {% if f_front == 'E-05' %}selected{% endif %}>E-05</option>
      <option value="E-06" {% if f_front == 'E-06' %}selected{% endif %}>E-06</option>
      <option value="E-09" {% if f_front == 'E-09' %}selected{% endif %}>E-09</option>
      <option value="E-10" {% if f_front == 'E-10' %}selected{% endif %}>E-10</option>
      <option value="E-13" {% if f_front == 'E-13' %}selected{% endif %}>E-13</option>
      <option value="E-14" {% if f_front == 'E-14' %}selected{% endif %}>E-14</option>
      <option value="E-15" {% if f_front == 'E-15' %}selected{% endif %}>E-15</option>
      <option value="E-16" {% if f_front == 'E-16' %}selected{% endif %}>E-16</option>
      <option value="E-17" {% if f_front == 'E-17' %}selected{% endif %}>E-17</option>
      <option value="E-18" {% if f_front == 'E-18' %}selected{% endif %}>E-18</option>
      <option value="E-19" {% if f_front == 'E-19' %}selected{% endif %}>E-19</option>
      <option value="E-20" {% if f_front == 'E-20' %}selected{% endif %}>E-20</option>
      <option value="E-21" {% if f_front == 'E-21' %}selected{% endif %}>E-21</option>
      <option value="E-22" {% if f_front == 'E-22' %}selected{% endif %}>E-22</option>
      <option value="E-23" {% if f_front == 'E-23' %}selected{% endif %}>E-23</option>
      <option value="E-24" {% if f_front == 'E-24' %}selected{% endif %}>E-24</option>
      <option value="E-25" {% if f_front == 'E-25' %}selected{% endif %}>E-25</option>
      <option value="E-26" {% if f_front == 'E-26' %}selected{% endif %}>E-26</option>
      <option value="E-27" {% if f_front == 'E-27' %}selected{% endif %}>E-27</option>
      <option value="E-28" {% if f_front == 'E-28' %}selected{% endif %}>E-28</option>
      <option value="E-29" {% if f_front == 'E-29' %}selected{% endif %}>E-29</option>
      <option value="E-30" {% if f_front == 'E-30' %}selected{% endif %}>E-30</option>
      <option value="E-31" {% if f_front == 'E-31' %}selected{% endif %}>E-31</option>
      <option value="E-32" {% if f_front == 'E-32' %}selected{% endif %}>E-32</option>
      <option value="E-33" {% if f_front == 'E-33' %}selected{% endif %}>E-33</option>
      <option value="E-34" {% if f_front == 'E-34' %}selected{% endif %}>E-34</option>
      <option value="E-35" {% if f_front == 'E-35' %}selected{% endif %}>E-35</option>
      <option value="E-37" {% if f_front == 'E-37' %}selected{% endif %}>E-37</option>
      <option value="E-38" {% if f_front == 'E-38' %}selected{% endif %}>E-38</option>
      <option value="E-40" {% if f_front == 'E-40' %}selected{% endif %}>E-40</option>
      <option value="E-41" {% if f_front == 'E-41' %}selected{% endif %}>E-41</option>
      <option value="E-42" {% if f_front == 'E-42' %}selected{% endif %}>E-42</option>
      <option value="E-43" {% if f_front == 'E-43' %}selected{% endif %}>E-43</option>
      <option value="E-44" {% if f_front == 'E-44' %}selected{% endif %}>E-44</option>
      <option value="E-45" {% if f_front == 'E-45' %}selected{% endif %}>E-45</option>
      <option value="E-46" {% if f_front == 'E-46' %}selected{% endif %}>E-46</option>
      <option value="E-47" {% if f_front == 'E-47' %}selected{% endif %}>E-47</option>
      <option value="E-50" {% if f_front == 'E-50' %}selected{% endif %}>E-50</option>
      <option value="E-51" {% if f_front == 'E-51' %}selected{% endif %}>E-51</option>
      <option value="E-52" {% if f_front == 'E-52' %}selected{% endif %}>E-52</option>
      <option value="E-53" {% if f_front == 'E-53' %}selected{% endif %}>E-53</option>
      <option value="E-54" {% if f_front == 'E-54' %}selected{% endif %}>E-54</option>
      <option value="E-55" {% if f_front == 'E-55' %}selected{% endif %}>E-55</option>
      <option value="E-56" {% if f_front == 'E-56' %}selected{% endif %}>E-56</option>
      <option value="E-57" {% if f_front == 'E-57' %}selected{% endif %}>E-57</option>
    </select>

    <label>デザインサンプル(前):</label>
    <select name="design_sample_front">
      <option value="" {% if not extracted_data['design_sample_front'] %}selected{% endif %}>選択してください</option>
      {% set ds_front = extracted_data['design_sample_front'] %}
      <option value="D-008" {% if ds_front == 'D-008' %}selected{% endif %}>D-008</option>
      <option value="D-009" {% if ds_front == 'D-009' %}selected{% endif %}>D-009</option>
      <option value="D-012" {% if ds_front == 'D-012' %}selected{% endif %}>D-012</option>
      <option value="D-013" {% if ds_front == 'D-013' %}selected{% endif %}>D-013</option>
      <option value="D-014" {% if ds_front == 'D-014' %}selected{% endif %}>D-014</option>
      <option value="D-015" {% if ds_front == 'D-015' %}selected{% endif %}>D-015</option>
      <option value="D-027" {% if ds_front == 'D-027' %}selected{% endif %}>D-027</option>
      <option value="D-028" {% if ds_front == 'D-028' %}selected{% endif %}>D-028</option>
      <option value="D-029" {% if ds_front == 'D-029' %}selected{% endif %}>D-029</option>
      <option value="D-030" {% if ds_front == 'D-030' %}selected{% endif %}>D-030</option>
      <option value="D-039" {% if ds_front == 'D-039' %}selected{% endif %}>D-039</option>
      <option value="D-040" {% if ds_front == 'D-040' %}selected{% endif %}>D-040</option>
      <option value="D-041" {% if ds_front == 'D-041' %}selected{% endif %}>D-041</option>
      <option value="D-042" {% if ds_front == 'D-042' %}selected{% endif %}>D-042</option>
      <option value="D-051" {% if ds_front == 'D-051' %}selected{% endif %}>D-051</option>
      <option value="D-068" {% if ds_front == 'D-068' %}selected{% endif %}>D-068</option>
      <option value="D-080" {% if ds_front == 'D-080' %}selected{% endif %}>D-080</option>
      <option value="D-106" {% if ds_front == 'D-106' %}selected{% endif %}>D-106</option>
      <option value="D-111" {% if ds_front == 'D-111' %}selected{% endif %}>D-111</option>
      <option value="D-125" {% if ds_front == 'D-125' %}selected{% endif %}>D-125</option>
      <option value="D-128" {% if ds_front == 'D-128' %}selected{% endif %}>D-128</option>
      <option value="D-129" {% if ds_front == 'D-129' %}selected{% endif %}>D-129</option>
      <option value="D-138" {% if ds_front == 'D-138' %}selected{% endif %}>D-138</option>
      <option value="D-140" {% if ds_front == 'D-140' %}selected{% endif %}>D-140</option>
      <option value="D-150" {% if ds_front == 'D-150' %}selected{% endif %}>D-150</option>
      <option value="D-157" {% if ds_front == 'D-157' %}selected{% endif %}>D-157</option>
      <option value="D-167" {% if ds_front == 'D-167' %}selected{% endif %}>D-167</option>
      <option value="D-168" {% if ds_front == 'D-168' %}selected{% endif %}>D-168</option>
      <option value="D-177" {% if ds_front == 'D-177' %}selected{% endif %}>D-177</option>
      <option value="D-195" {% if ds_front == 'D-195' %}selected{% endif %}>D-195</option>
      <option value="D-201" {% if ds_front == 'D-201' %}selected{% endif %}>D-201</option>
      <option value="D-212" {% if ds_front == 'D-212' %}selected{% endif %}>D-212</option>
      <option value="D-213" {% if ds_front == 'D-213' %}selected{% endif %}>D-213</option>
      <option value="D-218" {% if ds_front == 'D-218' %}selected{% endif %}>D-218</option>
      <option value="D-220" {% if ds_front == 'D-220' %}selected{% endif %}>D-220</option>
      <option value="D-222" {% if ds_front == 'D-222' %}selected{% endif %}>D-222</option>
      <option value="D-223" {% if ds_front == 'D-223' %}selected{% endif %}>D-223</option>
      <option value="D-229" {% if ds_front == 'D-229' %}selected{% endif %}>D-229</option>
      <option value="D-230" {% if ds_front == 'D-230' %}selected{% endif %}>D-230</option>
      <option value="D-231" {% if ds_front == 'D-231' %}selected{% endif %}>D-231</option>
      <option value="D-233" {% if ds_front == 'D-233' %}selected{% endif %}>D-233</option>
      <option value="D-234" {% if ds_front == 'D-234' %}selected{% endif %}>D-234</option>
      <option value="D-235" {% if ds_front == 'D-235' %}selected{% endif %}>D-235</option>
      <option value="D-236" {% if ds_front == 'D-236' %}selected{% endif %}>D-236</option>
      <option value="D-238" {% if ds_front == 'D-238' %}selected{% endif %}>D-238</option>
      <option value="D-240" {% if ds_front == 'D-240' %}selected{% endif %}>D-240</option>
      <option value="D-241" {% if ds_front == 'D-241' %}selected{% endif %}>D-241</option>
      <option value="D-242" {% if ds_front == 'D-242' %}selected{% endif %}>D-242</option>
      <option value="D-244" {% if ds_front == 'D-244' %}selected{% endif %}>D-244</option>
      <option value="D-246" {% if ds_front == 'D-246' %}selected{% endif %}>D-246</option>
      <option value="D-247" {% if ds_front == 'D-247' %}selected{% endif %}>D-247</option>
      <option value="D-248" {% if ds_front == 'D-248' %}selected{% endif %}>D-248</option>
      <option value="D-260" {% if ds_front == 'D-260' %}selected{% endif %}>D-260</option>
      <option value="D-266" {% if ds_front == 'D-266' %}selected{% endif %}>D-266</option>
      <option value="D-273" {% if ds_front == 'D-273' %}selected{% endif %}>D-273</option>
      <option value="D-274" {% if ds_front == 'D-274' %}selected{% endif %}>D-274</option>
      <option value="D-275" {% if ds_front == 'D-275' %}selected{% endif %}>D-275</option>
      <option value="D-280" {% if ds_front == 'D-280' %}selected{% endif %}>D-280</option>
      <option value="D-281" {% if ds_front == 'D-281' %}selected{% endif %}>D-281</option>
      <option value="D-286" {% if ds_front == 'D-286' %}selected{% endif %}>D-286</option>
      <option value="D-287" {% if ds_front == 'D-287' %}selected{% endif %}>D-287</option>
      <option value="D-288" {% if ds_front == 'D-288' %}selected{% endif %}>D-288</option>
      <option value="D-291" {% if ds_front == 'D-291' %}selected{% endif %}>D-291</option>
      <option value="D-292" {% if ds_front == 'D-292' %}selected{% endif %}>D-292</option>
      <option value="D-298" {% if ds_front == 'D-298' %}selected{% endif %}>D-298</option>
      <option value="D-299" {% if ds_front == 'D-299' %}selected{% endif %}>D-299</option>
      <option value="D-300" {% if ds_front == 'D-300' %}selected{% endif %}>D-300</option>
      <option value="D-301" {% if ds_front == 'D-301' %}selected{% endif %}>D-301</option>
      <option value="D-307" {% if ds_front == 'D-307' %}selected{% endif %}>D-307</option>
      <option value="D-309" {% if ds_front == 'D-309' %}selected{% endif %}>D-309</option>
      <option value="D-315" {% if ds_front == 'D-315' %}selected{% endif %}>D-315</option>
      <option value="D-317" {% if ds_front == 'D-317' %}selected{% endif %}>D-317</option>
      <option value="D-318" {% if ds_front == 'D-318' %}selected{% endif %}>D-318</option>
      <option value="D-322" {% if ds_front == 'D-322' %}selected{% endif %}>D-322</option>
      <option value="D-332" {% if ds_front == 'D-332' %}selected{% endif %}>D-332</option>
      <option value="D-334" {% if ds_front == 'D-334' %}selected{% endif %}>D-334</option>
      <option value="D-335" {% if ds_front == 'D-335' %}selected{% endif %}>D-335</option>
      <option value="D-337" {% if ds_front == 'D-337' %}selected{% endif %}>D-337</option>
      <option value="D-340" {% if ds_front == 'D-340' %}selected{% endif %}>D-340</option>
      <option value="D-341" {% if ds_front == 'D-341' %}selected{% endif %}>D-341</option>
      <option value="D-344" {% if ds_front == 'D-344' %}selected{% endif %}>D-344</option>
      <option value="D-346" {% if ds_front == 'D-346' %}selected{% endif %}>D-346</option>
      <option value="D-347" {% if ds_front == 'D-347' %}selected{% endif %}>D-347</option>
      <option value="D-348" {% if ds_front == 'D-348' %}selected{% endif %}>D-348</option>
      <option value="D-349" {% if ds_front == 'D-349' %}selected{% endif %}>D-349</option>
      <option value="D-352" {% if ds_front == 'D-352' %}selected{% endif %}>D-352</option>
      <option value="D-353" {% if ds_front == 'D-353' %}selected{% endif %}>D-353</option>
      <option value="D-354" {% if ds_front == 'D-354' %}selected{% endif %}>D-354</option>
      <option value="D-355" {% if ds_front == 'D-355' %}selected{% endif %}>D-355</option>
      <option value="D-358" {% if ds_front == 'D-358' %}selected{% endif %}>D-358</option>
      <option value="D-363" {% if ds_front == 'D-363' %}selected{% endif %}>D-363</option>
      <option value="D-364" {% if ds_front == 'D-364' %}selected{% endif %}>D-364</option>
      <option value="D-365" {% if ds_front == 'D-365' %}selected{% endif %}>D-365</option>
      <option value="D-366" {% if ds_front == 'D-366' %}selected{% endif %}>D-366</option>
      <option value="D-367" {% if ds_front == 'D-367' %}selected{% endif %}>D-367</option>
      <option value="D-368" {% if ds_front == 'D-368' %}selected{% endif %}>D-368</option>
      <option value="D-370" {% if ds_front == 'D-370' %}selected{% endif %}>D-370</option>
      <option value="D-372" {% if ds_front == 'D-372' %}selected{% endif %}>D-372</option>
      <option value="D-373" {% if ds_front == 'D-373' %}selected{% endif %}>D-373</option>
      <option value="D-374" {% if ds_front == 'D-374' %}selected{% endif %}>D-374</option>
      <option value="D-375" {% if ds_front == 'D-375' %}selected{% endif %}>D-375</option>
      <option value="D-376" {% if ds_front == 'D-376' %}selected{% endif %}>D-376</option>
      <option value="D-377" {% if ds_front == 'D-377' %}selected{% endif %}>D-377</option>
      <option value="D-378" {% if ds_front == 'D-378' %}selected{% endif %}>D-378</option>
      <option value="D-379" {% if ds_front == 'D-379' %}selected{% endif %}>D-379</option>
      <option value="D-380" {% if ds_front == 'D-380' %}selected{% endif %}>D-380</option>
      <option value="D-381" {% if ds_front == 'D-381' %}selected{% endif %}>D-381</option>
      <option value="D-382" {% if ds_front == 'D-382' %}selected{% endif %}>D-382</option>
      <option value="D-383" {% if ds_front == 'D-383' %}selected{% endif %}>D-383</option>
      <option value="D-384" {% if ds_front == 'D-384' %}selected{% endif %}>D-384</option>
      <option value="D-385" {% if ds_front == 'D-385' %}selected{% endif %}>D-385</option>
      <option value="D-386" {% if ds_front == 'D-386' %}selected{% endif %}>D-386</option>
      <option value="D-388" {% if ds_front == 'D-388' %}selected{% endif %}>D-388</option>
      <option value="D-390" {% if ds_front == 'D-390' %}selected{% endif %}>D-390</option>
      <option value="D-391" {% if ds_front == 'D-391' %}selected{% endif %}>D-391</option>
      <option value="D-392" {% if ds_front == 'D-392' %}selected{% endif %}>D-392</option>
      <option value="D-393" {% if ds_front == 'D-393' %}selected{% endif %}>D-393</option>
      <option value="D-394" {% if ds_front == 'D-394' %}selected{% endif %}>D-394</option>
      <option value="D-396" {% if ds_front == 'D-396' %}selected{% endif %}>D-396</option>
      <option value="D-397" {% if ds_front == 'D-397' %}selected{% endif %}>D-397</option>
      <option value="D-398" {% if ds_front == 'D-398' %}selected{% endif %}>D-398</option>
      <option value="D-399" {% if ds_front == 'D-399' %}selected{% endif %}>D-399</option>
      <option value="D-400" {% if ds_front == 'D-400' %}selected{% endif %}>D-400</option>
      <option value="D-401" {% if ds_front == 'D-401' %}selected{% endif %}>D-401</option>
      <option value="D-402" {% if ds_front == 'D-402' %}selected{% endif %}>D-402</option>
      <option value="D-403" {% if ds_front == 'D-403' %}selected{% endif %}>D-403</option>
      <option value="D-404" {% if ds_front == 'D-404' %}selected{% endif %}>D-404</option>
      <option value="D-405" {% if ds_front == 'D-405' %}selected{% endif %}>D-405</option>
    </select>
    </select>

    <label>カスタムプリントデータ(前) (画像アップロード):</label>
    <input type="file" name="position_data_front">
    </div>

    <!-- ▼▼ プリント位置(前) => 選択式に変更 ▼▼ -->
    <label>プリント位置(前):</label>
    <select name="front_positions_selected">
      <option value="">選択してください</option>
      {% set f_pos = extracted_data['front_positions_selected'] if extracted_data['front_positions_selected'] else '' %}
      <option value="左胸" {% if f_pos == '左胸' %}selected{% endif %}>左胸</option>
      <option value="右胸" {% if f_pos == '右胸' %}selected{% endif %}>右胸</option>
      <option value="中央" {% if f_pos == '中央' %}selected{% endif %}>中央</option>
      <option value="左下" {% if f_pos == '左下' %}selected{% endif %}>左下</option>
      <option value="中央(下)" {% if f_pos == '中央(下)' %}selected{% endif %}>中央(下)</option>
      <option value="右下" {% if f_pos == '右下' %}selected{% endif %}>右下</option>
    </select>


    <!-- ▼▼ 背面プリント ▼▼ -->
    <h3>プリント位置: 背中</h3>
    <div class="radio-group">
      <label>
        <input type="radio" name="print_size_back"
               value="おまかせ (最大:横28cm x 縦35cm以内)"
               {% if extracted_data['print_size_back'] == "おまかせ (最大:横28cm x 縦35cm以内)" or not extracted_data['print_size_back'] %}checked{% endif %}>
        おまかせ (最大:横28cm x 縦35cm以内)
      </label>
      <label>
        <input type="radio" name="print_size_back" value="custom"
          {% if extracted_data['print_size_back'] == "custom" %}checked{% endif %}>
        ヨコcm x タテcmくらい(入力する):
      </label>
    </div>
    <input type="text" name="print_size_back_custom"
           placeholder="例: 20cm x 15cm"
           value="{{ extracted_data['print_size_back_custom'] or '' }}">

    <!-- ▼▼ プリントカラー(背中) - シンプルな選択式 ▼▼ -->
    <label>プリントカラー(背中):</label>
    <select name="print_color_back[]" multiple onchange="limitSelection(this, 4)">
      <option value="" {% if not extracted_data['print_color_back'] %}selected{% endif %}>選択してください</option>
      {% set back_colors = extracted_data['print_color_back'] if extracted_data['print_color_back'] else [] %}
      <option value="ホワイト" {% if 'ホワイト' in back_colors %}selected{% endif %}>ホワイト</option>
      <option value="ライトグレー" {% if 'ライトグレー' in back_colors %}selected{% endif %}>ライトグレー</option>
      <option value="ダークグレー" {% if 'ダークグレー' in back_colors %}selected{% endif %}>ダークグレー</option>
      <option value="ブラック" {% if 'ブラック' in back_colors %}selected{% endif %}>ブラック</option>
      <option value="サックス" {% if 'サックス' in back_colors %}selected{% endif %}>サックス</option>
      <option value="ブルー" {% if 'ブルー' in back_colors %}selected{% endif %}>ブルー</option>
      <option value="ネイビー" {% if 'ネイビー' in back_colors %}selected{% endif %}>ネイビー</option>
      <option value="ライトピンク" {% if 'ライトピンク' in back_colors %}selected{% endif %}>ライトピンク</option>
      <option value="ローズピンク" {% if 'ローズピンク' in back_colors %}selected{% endif %}>ローズピンク</option>
      <option value="ホットピンク" {% if 'ホットピンク' in back_colors %}selected{% endif %}>ホットピンク</option>
      <option value="レッド" {% if 'レッド' in back_colors %}selected{% endif %}>レッド</option>
      <option value="ワインレッド" {% if 'ワインレッド' in back_colors %}selected{% endif %}>ワインレッド</option>
      <option value="ミントグリーン" {% if 'ミントグリーン' in back_colors %}selected{% endif %}>ミントグリーン</option>
      <option value="エメラルドグリーン" {% if 'エメラルドグリーン' in back_colors %}selected{% endif %}>エメラルドグリーン</option>
      <option value="パステルイエロー" {% if 'パステルイエロー' in back_colors %}selected{% endif %}>パステルイエロー</option>
      <option value="イエロー" {% if 'イエロー' in back_colors %}selected{% endif %}>イエロー</option>
      <option value="ゴールドイエロー" {% if 'ゴールドイエロー' in back_colors %}selected{% endif %}>ゴールドイエロー</option>
      <option value="オレンジ" {% if 'オレンジ' in back_colors %}selected{% endif %}>オレンジ</option>
      <option value="イエローグリーン" {% if 'イエローグリーン' in back_colors %}selected{% endif %}>イエローグリーン</option>
      <option value="グリーン" {% if 'グリーン' in back_colors %}selected{% endif %}>グリーン</option>
      <option value="ダークグリーン" {% if 'ダークグリーン' in back_colors %}selected{% endif %}>ダークグリーン</option>
      <option value="ライトパープル" {% if 'ライトパープル' in back_colors %}selected{% endif %}>ライトパープル</option>
      <option value="パープル" {% if 'パープル' in back_colors %}selected{% endif %}>パープル</option>
      <option value="クリーム" {% if 'クリーム' in back_colors %}selected{% endif %}>クリーム</option>
      <option value="ライトブラウン" {% if 'ライトブラウン' in back_colors %}selected{% endif %}>ライトブラウン</option>
      <option value="ダークブラウン" {% if 'ダークブラウン' in back_colors %}selected{% endif %}>ダークブラウン</option>
      <option value="シルバー" {% if 'シルバー' in back_colors %}selected{% endif %}>シルバー</option>
      <option value="ゴールド" {% if 'ゴールド' in back_colors %}selected{% endif %}>ゴールド</option>
      <option value="グリッターシルバー" {% if 'グリッターシルバー' in back_colors %}selected{% endif %}>グリッターシルバー</option>
      <option value="グリッターゴールド" {% if 'グリッターゴールド' in back_colors %}selected{% endif %}>グリッターゴールド</option>
      <option value="グリッターブラック" {% if 'グリッターブラック' in back_colors %}selected{% endif %}>グリッターブラック</option>
      <option value="グリッターイエロー" {% if 'グリッターイエロー' in back_colors %}selected{% endif %}>グリッターイエロー</option>
      <option value="グリッターピンク" {% if 'グリッターピンク' in back_colors %}selected{% endif %}>グリッターピンク</option>
      <option value="グリッターレッド" {% if 'グリッターレッド' in back_colors %}selected{% endif %}>グリッターレッド</option>
      <option value="グリッターグリーン" {% if 'グリッターグリーン' in back_colors %}selected{% endif %}>グリッターグリーン</option>
      <option value="グリッターブルー" {% if 'グリッターブルー' in back_colors %}selected{% endif %}>グリッターブルー</option>
      <option value="グリッターパープル" {% if 'グリッターパープル' in back_colors %}selected{% endif %}>グリッターパープル</option>
      <option value="蛍光オレンジ" {% if '蛍光オレンジ' in back_colors %}selected{% endif %}>蛍光オレンジ</option>
      <option value="蛍光ピンク" {% if '蛍光ピンク' in back_colors %}selected{% endif %}>蛍光ピンク</option>
      <option value="蛍光グリーン" {% if '蛍光グリーン' in back_colors %}selected{% endif %}>蛍光グリーン</option>
      <option value="フルカラー(小)" {% if 'フルカラー(小)' in back_colors %}selected{% endif %}>フルカラー(小)</option>
      <option value="フルカラー(中)" {% if 'フルカラー(中)' in back_colors %}selected{% endif %}>フルカラー(中)</option>
      <option value="フルカラー(大)" {% if 'フルカラー(大)' in back_colors %}selected{% endif %}>フルカラー(大)</option>
    </select>

    <label>フォントNo.(背中):</label>
    <select name="font_no_back">
      <option value="" {% if not extracted_data['font_no_back'] %}selected{% endif %}>選択してください</option>
      {% set f_back = extracted_data['font_no_back'] %}
      <option value="E-01" {% if f_front == 'E-01' %}selected{% endif %}>E-01</option>
      <option value="E-02" {% if f_front == 'E-02' %}selected{% endif %}>E-02</option>
      <option value="E-03" {% if f_front == 'E-03' %}selected{% endif %}>E-03</option>
      <option value="E-05" {% if f_front == 'E-05' %}selected{% endif %}>E-05</option>
      <option value="E-06" {% if f_front == 'E-06' %}selected{% endif %}>E-06</option>
      <option value="E-09" {% if f_front == 'E-09' %}selected{% endif %}>E-09</option>
      <option value="E-10" {% if f_front == 'E-10' %}selected{% endif %}>E-10</option>
      <option value="E-13" {% if f_front == 'E-13' %}selected{% endif %}>E-13</option>
      <option value="E-14" {% if f_front == 'E-14' %}selected{% endif %}>E-14</option>
      <option value="E-15" {% if f_front == 'E-15' %}selected{% endif %}>E-15</option>
      <option value="E-16" {% if f_front == 'E-16' %}selected{% endif %}>E-16</option>
      <option value="E-17" {% if f_front == 'E-17' %}selected{% endif %}>E-17</option>
      <option value="E-18" {% if f_front == 'E-18' %}selected{% endif %}>E-18</option>
      <option value="E-19" {% if f_front == 'E-19' %}selected{% endif %}>E-19</option>
      <option value="E-20" {% if f_front == 'E-20' %}selected{% endif %}>E-20</option>
      <option value="E-21" {% if f_front == 'E-21' %}selected{% endif %}>E-21</option>
      <option value="E-22" {% if f_front == 'E-22' %}selected{% endif %}>E-22</option>
      <option value="E-23" {% if f_front == 'E-23' %}selected{% endif %}>E-23</option>
      <option value="E-24" {% if f_front == 'E-24' %}selected{% endif %}>E-24</option>
      <option value="E-25" {% if f_front == 'E-25' %}selected{% endif %}>E-25</option>
      <option value="E-26" {% if f_front == 'E-26' %}selected{% endif %}>E-26</option>
      <option value="E-27" {% if f_front == 'E-27' %}selected{% endif %}>E-27</option>
      <option value="E-28" {% if f_front == 'E-28' %}selected{% endif %}>E-28</option>
      <option value="E-29" {% if f_front == 'E-29' %}selected{% endif %}>E-29</option>
      <option value="E-30" {% if f_front == 'E-30' %}selected{% endif %}>E-30</option>
      <option value="E-31" {% if f_front == 'E-31' %}selected{% endif %}>E-31</option>
      <option value="E-32" {% if f_front == 'E-32' %}selected{% endif %}>E-32</option>
      <option value="E-33" {% if f_front == 'E-33' %}selected{% endif %}>E-33</option>
      <option value="E-34" {% if f_front == 'E-34' %}selected{% endif %}>E-34</option>
      <option value="E-35" {% if f_front == 'E-35' %}selected{% endif %}>E-35</option>
      <option value="E-37" {% if f_front == 'E-37' %}selected{% endif %}>E-37</option>
      <option value="E-38" {% if f_front == 'E-38' %}selected{% endif %}>E-38</option>
      <option value="E-40" {% if f_front == 'E-40' %}selected{% endif %}>E-40</option>
      <option value="E-41" {% if f_front == 'E-41' %}selected{% endif %}>E-41</option>
      <option value="E-42" {% if f_front == 'E-42' %}selected{% endif %}>E-42</option>
      <option value="E-43" {% if f_front == 'E-43' %}selected{% endif %}>E-43</option>
      <option value="E-44" {% if f_front == 'E-44' %}selected{% endif %}>E-44</option>
      <option value="E-45" {% if f_front == 'E-45' %}selected{% endif %}>E-45</option>
      <option value="E-46" {% if f_front == 'E-46' %}selected{% endif %}>E-46</option>
      <option value="E-47" {% if f_front == 'E-47' %}selected{% endif %}>E-47</option>
      <option value="E-50" {% if f_front == 'E-50' %}selected{% endif %}>E-50</option>
      <option value="E-51" {% if f_front == 'E-51' %}selected{% endif %}>E-51</option>
      <option value="E-52" {% if f_front == 'E-52' %}selected{% endif %}>E-52</option>
      <option value="E-53" {% if f_front == 'E-53' %}selected{% endif %}>E-53</option>
      <option value="E-54" {% if f_front == 'E-54' %}selected{% endif %}>E-54</option>
      <option value="E-55" {% if f_front == 'E-55' %}selected{% endif %}>E-55</option>
      <option value="E-56" {% if f_front == 'E-56' %}selected{% endif %}>E-56</option>
      <option value="E-57" {% if f_front == 'E-57' %}selected{% endif %}>E-57</option>
    </select>

    <label>デザインサンプル(背中):</label>
    <select name="design_sample_back">
      <option value="" {% if not extracted_data['design_sample_back'] %}selected{% endif %}>選択してください</option>
      {% set ds_back = extracted_data['design_sample_back'] %}
      <option value="D-008" {% if ds_front == 'D-008' %}selected{% endif %}>D-008</option>
      <option value="D-009" {% if ds_front == 'D-009' %}selected{% endif %}>D-009</option>
      <option value="D-012" {% if ds_front == 'D-012' %}selected{% endif %}>D-012</option>
      <option value="D-013" {% if ds_front == 'D-013' %}selected{% endif %}>D-013</option>
      <option value="D-014" {% if ds_front == 'D-014' %}selected{% endif %}>D-014</option>
      <option value="D-015" {% if ds_front == 'D-015' %}selected{% endif %}>D-015</option>
      <option value="D-027" {% if ds_front == 'D-027' %}selected{% endif %}>D-027</option>
      <option value="D-028" {% if ds_front == 'D-028' %}selected{% endif %}>D-028</option>
      <option value="D-029" {% if ds_front == 'D-029' %}selected{% endif %}>D-029</option>
      <option value="D-030" {% if ds_front == 'D-030' %}selected{% endif %}>D-030</option>
      <option value="D-039" {% if ds_front == 'D-039' %}selected{% endif %}>D-039</option>
      <option value="D-040" {% if ds_front == 'D-040' %}selected{% endif %}>D-040</option>
      <option value="D-041" {% if ds_front == 'D-041' %}selected{% endif %}>D-041</option>
      <option value="D-042" {% if ds_front == 'D-042' %}selected{% endif %}>D-042</option>
      <option value="D-051" {% if ds_front == 'D-051' %}selected{% endif %}>D-051</option>
      <option value="D-068" {% if ds_front == 'D-068' %}selected{% endif %}>D-068</option>
      <option value="D-080" {% if ds_front == 'D-080' %}selected{% endif %}>D-080</option>
      <option value="D-106" {% if ds_front == 'D-106' %}selected{% endif %}>D-106</option>
      <option value="D-111" {% if ds_front == 'D-111' %}selected{% endif %}>D-111</option>
      <option value="D-125" {% if ds_front == 'D-125' %}selected{% endif %}>D-125</option>
      <option value="D-128" {% if ds_front == 'D-128' %}selected{% endif %}>D-128</option>
      <option value="D-129" {% if ds_front == 'D-129' %}selected{% endif %}>D-129</option>
      <option value="D-138" {% if ds_front == 'D-138' %}selected{% endif %}>D-138</option>
      <option value="D-140" {% if ds_front == 'D-140' %}selected{% endif %}>D-140</option>
      <option value="D-150" {% if ds_front == 'D-150' %}selected{% endif %}>D-150</option>
      <option value="D-157" {% if ds_front == 'D-157' %}selected{% endif %}>D-157</option>
      <option value="D-167" {% if ds_front == 'D-167' %}selected{% endif %}>D-167</option>
      <option value="D-168" {% if ds_front == 'D-168' %}selected{% endif %}>D-168</option>
      <option value="D-177" {% if ds_front == 'D-177' %}selected{% endif %}>D-177</option>
      <option value="D-195" {% if ds_front == 'D-195' %}selected{% endif %}>D-195</option>
      <option value="D-201" {% if ds_front == 'D-201' %}selected{% endif %}>D-201</option>
      <option value="D-212" {% if ds_front == 'D-212' %}selected{% endif %}>D-212</option>
      <option value="D-213" {% if ds_front == 'D-213' %}selected{% endif %}>D-213</option>
      <option value="D-218" {% if ds_front == 'D-218' %}selected{% endif %}>D-218</option>
      <option value="D-220" {% if ds_front == 'D-220' %}selected{% endif %}>D-220</option>
      <option value="D-222" {% if ds_front == 'D-222' %}selected{% endif %}>D-222</option>
      <option value="D-223" {% if ds_front == 'D-223' %}selected{% endif %}>D-223</option>
      <option value="D-229" {% if ds_front == 'D-229' %}selected{% endif %}>D-229</option>
      <option value="D-230" {% if ds_front == 'D-230' %}selected{% endif %}>D-230</option>
      <option value="D-231" {% if ds_front == 'D-231' %}selected{% endif %}>D-231</option>
      <option value="D-233" {% if ds_front == 'D-233' %}selected{% endif %}>D-233</option>
      <option value="D-234" {% if ds_front == 'D-234' %}selected{% endif %}>D-234</option>
      <option value="D-235" {% if ds_front == 'D-235' %}selected{% endif %}>D-235</option>
      <option value="D-236" {% if ds_front == 'D-236' %}selected{% endif %}>D-236</option>
      <option value="D-238" {% if ds_front == 'D-238' %}selected{% endif %}>D-238</option>
      <option value="D-240" {% if ds_front == 'D-240' %}selected{% endif %}>D-240</option>
      <option value="D-241" {% if ds_front == 'D-241' %}selected{% endif %}>D-241</option>
      <option value="D-242" {% if ds_front == 'D-242' %}selected{% endif %}>D-242</option>
      <option value="D-244" {% if ds_front == 'D-244' %}selected{% endif %}>D-244</option>
      <option value="D-246" {% if ds_front == 'D-246' %}selected{% endif %}>D-246</option>
      <option value="D-247" {% if ds_front == 'D-247' %}selected{% endif %}>D-247</option>
      <option value="D-248" {% if ds_front == 'D-248' %}selected{% endif %}>D-248</option>
      <option value="D-260" {% if ds_front == 'D-260' %}selected{% endif %}>D-260</option>
      <option value="D-266" {% if ds_front == 'D-266' %}selected{% endif %}>D-266</option>
      <option value="D-273" {% if ds_front == 'D-273' %}selected{% endif %}>D-273</option>
      <option value="D-274" {% if ds_front == 'D-274' %}selected{% endif %}>D-274</option>
      <option value="D-275" {% if ds_front == 'D-275' %}selected{% endif %}>D-275</option>
      <option value="D-280" {% if ds_front == 'D-280' %}selected{% endif %}>D-280</option>
      <option value="D-281" {% if ds_front == 'D-281' %}selected{% endif %}>D-281</option>
      <option value="D-286" {% if ds_front == 'D-286' %}selected{% endif %}>D-286</option>
      <option value="D-287" {% if ds_front == 'D-287' %}selected{% endif %}>D-287</option>
      <option value="D-288" {% if ds_front == 'D-288' %}selected{% endif %}>D-288</option>
      <option value="D-291" {% if ds_front == 'D-291' %}selected{% endif %}>D-291</option>
      <option value="D-292" {% if ds_front == 'D-292' %}selected{% endif %}>D-292</option>
      <option value="D-298" {% if ds_front == 'D-298' %}selected{% endif %}>D-298</option>
      <option value="D-299" {% if ds_front == 'D-299' %}selected{% endif %}>D-299</option>
      <option value="D-300" {% if ds_front == 'D-300' %}selected{% endif %}>D-300</option>
      <option value="D-301" {% if ds_front == 'D-301' %}selected{% endif %}>D-301</option>
      <option value="D-307" {% if ds_front == 'D-307' %}selected{% endif %}>D-307</option>
      <option value="D-309" {% if ds_front == 'D-309' %}selected{% endif %}>D-309</option>
      <option value="D-315" {% if ds_front == 'D-315' %}selected{% endif %}>D-315</option>
      <option value="D-317" {% if ds_front == 'D-317' %}selected{% endif %}>D-317</option>
      <option value="D-318" {% if ds_front == 'D-318' %}selected{% endif %}>D-318</option>
      <option value="D-322" {% if ds_front == 'D-322' %}selected{% endif %}>D-322</option>
      <option value="D-332" {% if ds_front == 'D-332' %}selected{% endif %}>D-332</option>
      <option value="D-334" {% if ds_front == 'D-334' %}selected{% endif %}>D-334</option>
      <option value="D-335" {% if ds_front == 'D-335' %}selected{% endif %}>D-335</option>
      <option value="D-337" {% if ds_front == 'D-337' %}selected{% endif %}>D-337</option>
      <option value="D-340" {% if ds_front == 'D-340' %}selected{% endif %}>D-340</option>
      <option value="D-341" {% if ds_front == 'D-341' %}selected{% endif %}>D-341</option>
      <option value="D-344" {% if ds_front == 'D-344' %}selected{% endif %}>D-344</option>
      <option value="D-346" {% if ds_front == 'D-346' %}selected{% endif %}>D-346</option>
      <option value="D-347" {% if ds_front == 'D-347' %}selected{% endif %}>D-347</option>
      <option value="D-348" {% if ds_front == 'D-348' %}selected{% endif %}>D-348</option>
      <option value="D-349" {% if ds_front == 'D-349' %}selected{% endif %}>D-349</option>
      <option value="D-352" {% if ds_front == 'D-352' %}selected{% endif %}>D-352</option>
      <option value="D-353" {% if ds_front == 'D-353' %}selected{% endif %}>D-353</option>
      <option value="D-354" {% if ds_front == 'D-354' %}selected{% endif %}>D-354</option>
      <option value="D-355" {% if ds_front == 'D-355' %}selected{% endif %}>D-355</option>
      <option value="D-358" {% if ds_front == 'D-358' %}selected{% endif %}>D-358</option>
      <option value="D-363" {% if ds_front == 'D-363' %}selected{% endif %}>D-363</option>
      <option value="D-364" {% if ds_front == 'D-364' %}selected{% endif %}>D-364</option>
      <option value="D-365" {% if ds_front == 'D-365' %}selected{% endif %}>D-365</option>
      <option value="D-366" {% if ds_front == 'D-366' %}selected{% endif %}>D-366</option>
      <option value="D-367" {% if ds_front == 'D-367' %}selected{% endif %}>D-367</option>
      <option value="D-368" {% if ds_front == 'D-368' %}selected{% endif %}>D-368</option>
      <option value="D-370" {% if ds_front == 'D-370' %}selected{% endif %}>D-370</option>
      <option value="D-372" {% if ds_front == 'D-372' %}selected{% endif %}>D-372</option>
      <option value="D-373" {% if ds_front == 'D-373' %}selected{% endif %}>D-373</option>
      <option value="D-374" {% if ds_front == 'D-374' %}selected{% endif %}>D-374</option>
      <option value="D-375" {% if ds_front == 'D-375' %}selected{% endif %}>D-375</option>
      <option value="D-376" {% if ds_front == 'D-376' %}selected{% endif %}>D-376</option>
      <option value="D-377" {% if ds_front == 'D-377' %}selected{% endif %}>D-377</option>
      <option value="D-378" {% if ds_front == 'D-378' %}selected{% endif %}>D-378</option>
      <option value="D-379" {% if ds_front == 'D-379' %}selected{% endif %}>D-379</option>
      <option value="D-380" {% if ds_front == 'D-380' %}selected{% endif %}>D-380</option>
      <option value="D-381" {% if ds_front == 'D-381' %}selected{% endif %}>D-381</option>
      <option value="D-382" {% if ds_front == 'D-382' %}selected{% endif %}>D-382</option>
      <option value="D-383" {% if ds_front == 'D-383' %}selected{% endif %}>D-383</option>
      <option value="D-384" {% if ds_front == 'D-384' %}selected{% endif %}>D-384</option>
      <option value="D-385" {% if ds_front == 'D-385' %}selected{% endif %}>D-385</option>
      <option value="D-386" {% if ds_front == 'D-386' %}selected{% endif %}>D-386</option>
      <option value="D-388" {% if ds_front == 'D-388' %}selected{% endif %}>D-388</option>
      <option value="D-390" {% if ds_front == 'D-390' %}selected{% endif %}>D-390</option>
      <option value="D-391" {% if ds_front == 'D-391' %}selected{% endif %}>D-391</option>
      <option value="D-392" {% if ds_front == 'D-392' %}selected{% endif %}>D-392</option>
      <option value="D-393" {% if ds_front == 'D-393' %}selected{% endif %}>D-393</option>
      <option value="D-394" {% if ds_front == 'D-394' %}selected{% endif %}>D-394</option>
      <option value="D-396" {% if ds_front == 'D-396' %}selected{% endif %}>D-396</option>
      <option value="D-397" {% if ds_front == 'D-397' %}selected{% endif %}>D-397</option>
      <option value="D-398" {% if ds_front == 'D-398' %}selected{% endif %}>D-398</option>
      <option value="D-399" {% if ds_front == 'D-399' %}selected{% endif %}>D-399</option>
      <option value="D-400" {% if ds_front == 'D-400' %}selected{% endif %}>D-400</option>
      <option value="D-401" {% if ds_front == 'D-401' %}selected{% endif %}>D-401</option>
      <option value="D-402" {% if ds_front == 'D-402' %}selected{% endif %}>D-402</option>
      <option value="D-403" {% if ds_front == 'D-403' %}selected{% endif %}>D-403</option>
      <option value="D-404" {% if ds_front == 'D-404' %}selected{% endif %}>D-404</option>
      <option value="D-405" {% if ds_front == 'D-405' %}selected{% endif %}>D-405</option>
    </select>
    </select>

    <label>カスタムプリントデータ(背中) (画像アップロード):</label>
    <input type="file" name="position_data_back">
    </div>

    <!-- ▼▼ プリント位置(背中) => 選択式に変更 ▼▼ -->
    <label>プリント位置(背中):</label>
    <select name="back_positions_selected">
      <option value="">選択してください</option>
      {% set b_pos = extracted_data['back_positions_selected'] if extracted_data['back_positions_selected'] else '' %}
      <option value="首下" {% if b_pos == '首下' %}selected{% endif %}>首下</option>
      <option value="中央" {% if b_pos == '中央' %}selected{% endif %}>中央</option>
      <option value="左下" {% if b_pos == '左下' %}selected{% endif %}>左下</option>
      <option value="中央(下)" {% if b_pos == '中央(下)' %}selected{% endif %}>中央(下)</option>
      <option value="右下" {% if b_pos == '右下' %}selected{% endif %}>右下</option>
    </select>


    <!-- ▼▼ その他プリント ▼▼ -->
    <h3>プリント位置: その他</h3>
    <div class="radio-group">
      <label>
        <input type="radio" name="print_size_other" value="おまかせ (最大:横28cm x 縦35cm以内)"
          {% if extracted_data['print_size_other'] == "おまかせ (最大:横28cm x 縦35cm以内)" or not extracted_data['print_size_other'] %}checked{% endif %}>
        おまかせ (最大:横28cm x 縦35cm以内)
      </label>
      <label>
        <input type="radio" name="print_size_other" value="custom"
          {% if extracted_data['print_size_other'] == 'custom' %}checked{% endif %}>
        ヨコcm x タテcmくらい(入力する):
      </label>
    </div>
    <input type="text" name="print_size_other_custom" placeholder="例: 20cm x 15cm"
           value="{{ extracted_data['print_size_other_custom'] or '' }}">

    <!-- ▼▼ プリントカラー(その他) - シンプルな選択式 (複数選択) ▼▼ -->
    <label>プリントカラー(その他):</label>
    <select name="print_color_other[]" multiple onchange="limitSelection(this, 4)">
      <option value="" {% if not extracted_data['print_color_other'] %}selected{% endif %}>選択してください</option>
      {% set other_colors = extracted_data['print_color_other'] if extracted_data['print_color_other'] else [] %}
      <option value="ホワイト" {% if 'ホワイト' in other_colors %}selected{% endif %}>ホワイト</option>
      <option value="ライトグレー" {% if 'ライトグレー' in other_colors %}selected{% endif %}>ライトグレー</option>
      <option value="ダークグレー" {% if 'ダークグレー' in other_colors %}selected{% endif %}>ダークグレー</option>
      <option value="ブラック" {% if 'ブラック' in other_colors %}selected{% endif %}>ブラック</option>
      <option value="サックス" {% if 'サックス' in other_colors %}selected{% endif %}>サックス</option>
      <option value="ブルー" {% if 'ブルー' in other_colors %}selected{% endif %}>ブルー</option>
      <option value="ネイビー" {% if 'ネイビー' in other_colors %}selected{% endif %}>ネイビー</option>
      <option value="ライトピンク" {% if 'ライトピンク' in other_colors %}selected{% endif %}>ライトピンク</option>
      <option value="ローズピンク" {% if 'ローズピンク' in other_colors %}selected{% endif %}>ローズピンク</option>
      <option value="ホットピンク" {% if 'ホットピンク' in other_colors %}selected{% endif %}>ホットピンク</option>
      <option value="レッド" {% if 'レッド' in other_colors %}selected{% endif %}>レッド</option>
      <option value="ワインレッド" {% if 'ワインレッド' in other_colors %}selected{% endif %}>ワインレッド</option>
      <option value="ミントグリーン" {% if 'ミントグリーン' in other_colors %}selected{% endif %}>ミントグリーン</option>
      <option value="エメラルドグリーン" {% if 'エメラルドグリーン' in other_colors %}selected{% endif %}>エメラルドグリーン</option>
      <option value="パステルイエロー" {% if 'パステルイエロー' in other_colors %}selected{% endif %}>パステルイエロー</option>
      <option value="イエロー" {% if 'イエロー' in other_colors %}selected{% endif %}>イエロー</option>
      <option value="ゴールドイエロー" {% if 'ゴールドイエロー' in other_colors %}selected{% endif %}>ゴールドイエロー</option>
      <option value="オレンジ" {% if 'オレンジ' in other_colors %}selected{% endif %}>オレンジ</option>
      <option value="イエローグリーン" {% if 'イエローグリーン' in other_colors %}selected{% endif %}>イエローグリーン</option>
      <option value="グリーン" {% if 'グリーン' in other_colors %}selected{% endif %}>グリーン</option>
      <option value="ダークグリーン" {% if 'ダークグリーン' in other_colors %}selected{% endif %}>ダークグリーン</option>
      <option value="ライトパープル" {% if 'ライトパープル' in other_colors %}selected{% endif %}>ライトパープル</option>
      <option value="パープル" {% if 'パープル' in other_colors %}selected{% endif %}>パープル</option>
      <option value="クリーム" {% if 'クリーム' in other_colors %}selected{% endif %}>クリーム</option>
      <option value="ライトブラウン" {% if 'ライトブラウン' in other_colors %}selected{% endif %}>ライトブラウン</option>
      <option value="ダークブラウン" {% if 'ダークブラウン' in other_colors %}selected{% endif %}>ダークブラウン</option>
      <option value="シルバー" {% if 'シルバー' in other_colors %}selected{% endif %}>シルバー</option>
      <option value="ゴールド" {% if 'ゴールド' in other_colors %}selected{% endif %}>ゴールド</option>
      <option value="グリッターシルバー" {% if 'グリッターシルバー' in other_colors %}selected{% endif %}>グリッターシルバー</option>
      <option value="グリッターゴールド" {% if 'グリッターゴールド' in other_colors %}selected{% endif %}>グリッターゴールド</option>
      <option value="グリッターブラック" {% if 'グリッターブラック' in other_colors %}selected{% endif %}>グリッターブラック</option>
      <option value="グリッターイエロー" {% if 'グリッターイエロー' in other_colors %}selected{% endif %}>グリッターイエロー</option>
      <option value="グリッターピンク" {% if 'グリッターピンク' in other_colors %}selected{% endif %}>グリッターピンク</option>
      <option value="グリッターレッド" {% if 'グリッターレッド' in other_colors %}selected{% endif %}>グリッターレッド</option>
      <option value="グリッターグリーン" {% if 'グリッターグリーン' in other_colors %}selected{% endif %}>グリッターグリーン</option>
      <option value="グリッターブルー" {% if 'グリッターブルー' in other_colors %}selected{% endif %}>グリッターブルー</option>
      <option value="グリッターパープル" {% if 'グリッターパープル' in other_colors %}selected{% endif %}>グリッターパープル</option>
      <option value="蛍光オレンジ" {% if '蛍光オレンジ' in other_colors %}selected{% endif %}>蛍光オレンジ</option>
      <option value="蛍光ピンク" {% if '蛍光ピンク' in other_colors %}selected{% endif %}>蛍光ピンク</option>
      <option value="蛍光グリーン" {% if '蛍光グリーン' in other_colors %}selected{% endif %}>蛍光グリーン</option>
      <option value="フルカラー(小)" {% if 'フルカラー(小)' in other_colors %}selected{% endif %}>フルカラー(小)</option>
      <option value="フルカラー(中)" {% if 'フルカラー(中)' in other_colors %}selected{% endif %}>フルカラー(中)</option>
      <option value="フルカラー(大)" {% if 'フルカラー(大)' in other_colors %}selected{% endif %}>フルカラー(大)</option>
    </select>

    <label>フォントNo.(その他):</label>
    <select name="font_no_other">
      <option value="" {% if not extracted_data['font_no_other'] %}selected{% endif %}>選択してください</option>
      {% set f_other = extracted_data['font_no_other'] %}
      <option value="E-01" {% if f_front == 'E-01' %}selected{% endif %}>E-01</option>
      <option value="E-02" {% if f_front == 'E-02' %}selected{% endif %}>E-02</option>
      <option value="E-03" {% if f_front == 'E-03' %}selected{% endif %}>E-03</option>
      <option value="E-05" {% if f_front == 'E-05' %}selected{% endif %}>E-05</option>
      <option value="E-06" {% if f_front == 'E-06' %}selected{% endif %}>E-06</option>
      <option value="E-09" {% if f_front == 'E-09' %}selected{% endif %}>E-09</option>
      <option value="E-10" {% if f_front == 'E-10' %}selected{% endif %}>E-10</option>
      <option value="E-13" {% if f_front == 'E-13' %}selected{% endif %}>E-13</option>
      <option value="E-14" {% if f_front == 'E-14' %}selected{% endif %}>E-14</option>
      <option value="E-15" {% if f_front == 'E-15' %}selected{% endif %}>E-15</option>
      <option value="E-16" {% if f_front == 'E-16' %}selected{% endif %}>E-16</option>
      <option value="E-17" {% if f_front == 'E-17' %}selected{% endif %}>E-17</option>
      <option value="E-18" {% if f_front == 'E-18' %}selected{% endif %}>E-18</option>
      <option value="E-19" {% if f_front == 'E-19' %}selected{% endif %}>E-19</option>
      <option value="E-20" {% if f_front == 'E-20' %}selected{% endif %}>E-20</option>
      <option value="E-21" {% if f_front == 'E-21' %}selected{% endif %}>E-21</option>
      <option value="E-22" {% if f_front == 'E-22' %}selected{% endif %}>E-22</option>
      <option value="E-23" {% if f_front == 'E-23' %}selected{% endif %}>E-23</option>
      <option value="E-24" {% if f_front == 'E-24' %}selected{% endif %}>E-24</option>
      <option value="E-25" {% if f_front == 'E-25' %}selected{% endif %}>E-25</option>
      <option value="E-26" {% if f_front == 'E-26' %}selected{% endif %}>E-26</option>
      <option value="E-27" {% if f_front == 'E-27' %}selected{% endif %}>E-27</option>
      <option value="E-28" {% if f_front == 'E-28' %}selected{% endif %}>E-28</option>
      <option value="E-29" {% if f_front == 'E-29' %}selected{% endif %}>E-29</option>
      <option value="E-30" {% if f_front == 'E-30' %}selected{% endif %}>E-30</option>
      <option value="E-31" {% if f_front == 'E-31' %}selected{% endif %}>E-31</option>
      <option value="E-32" {% if f_front == 'E-32' %}selected{% endif %}>E-32</option>
      <option value="E-33" {% if f_front == 'E-33' %}selected{% endif %}>E-33</option>
      <option value="E-34" {% if f_front == 'E-34' %}selected{% endif %}>E-34</option>
      <option value="E-35" {% if f_front == 'E-35' %}selected{% endif %}>E-35</option>
      <option value="E-37" {% if f_front == 'E-37' %}selected{% endif %}>E-37</option>
      <option value="E-38" {% if f_front == 'E-38' %}selected{% endif %}>E-38</option>
      <option value="E-40" {% if f_front == 'E-40' %}selected{% endif %}>E-40</option>
      <option value="E-41" {% if f_front == 'E-41' %}selected{% endif %}>E-41</option>
      <option value="E-42" {% if f_front == 'E-42' %}selected{% endif %}>E-42</option>
      <option value="E-43" {% if f_front == 'E-43' %}selected{% endif %}>E-43</option>
      <option value="E-44" {% if f_front == 'E-44' %}selected{% endif %}>E-44</option>
      <option value="E-45" {% if f_front == 'E-45' %}selected{% endif %}>E-45</option>
      <option value="E-46" {% if f_front == 'E-46' %}selected{% endif %}>E-46</option>
      <option value="E-47" {% if f_front == 'E-47' %}selected{% endif %}>E-47</option>
      <option value="E-50" {% if f_front == 'E-50' %}selected{% endif %}>E-50</option>
      <option value="E-51" {% if f_front == 'E-51' %}selected{% endif %}>E-51</option>
      <option value="E-52" {% if f_front == 'E-52' %}selected{% endif %}>E-52</option>
      <option value="E-53" {% if f_front == 'E-53' %}selected{% endif %}>E-53</option>
      <option value="E-54" {% if f_front == 'E-54' %}selected{% endif %}>E-54</option>
      <option value="E-55" {% if f_front == 'E-55' %}selected{% endif %}>E-55</option>
      <option value="E-56" {% if f_front == 'E-56' %}selected{% endif %}>E-56</option>
      <option value="E-57" {% if f_front == 'E-57' %}selected{% endif %}>E-57</option>
    </select>

    <label>デザインサンプル(その他):</label>
    <select name="design_sample_other">
      <option value="" {% if not extracted_data['design_sample_other'] %}selected{% endif %}>選択してください</option>
      {% set ds_other = extracted_data['design_sample_other'] %}
      <option value="D-008" {% if ds_front == 'D-008' %}selected{% endif %}>D-008</option>
      <option value="D-009" {% if ds_front == 'D-009' %}selected{% endif %}>D-009</option>
      <option value="D-012" {% if ds_front == 'D-012' %}selected{% endif %}>D-012</option>
      <option value="D-013" {% if ds_front == 'D-013' %}selected{% endif %}>D-013</option>
      <option value="D-014" {% if ds_front == 'D-014' %}selected{% endif %}>D-014</option>
      <option value="D-015" {% if ds_front == 'D-015' %}selected{% endif %}>D-015</option>
      <option value="D-027" {% if ds_front == 'D-027' %}selected{% endif %}>D-027</option>
      <option value="D-028" {% if ds_front == 'D-028' %}selected{% endif %}>D-028</option>
      <option value="D-029" {% if ds_front == 'D-029' %}selected{% endif %}>D-029</option>
      <option value="D-030" {% if ds_front == 'D-030' %}selected{% endif %}>D-030</option>
      <option value="D-039" {% if ds_front == 'D-039' %}selected{% endif %}>D-039</option>
      <option value="D-040" {% if ds_front == 'D-040' %}selected{% endif %}>D-040</option>
      <option value="D-041" {% if ds_front == 'D-041' %}selected{% endif %}>D-041</option>
      <option value="D-042" {% if ds_front == 'D-042' %}selected{% endif %}>D-042</option>
      <option value="D-051" {% if ds_front == 'D-051' %}selected{% endif %}>D-051</option>
      <option value="D-068" {% if ds_front == 'D-068' %}selected{% endif %}>D-068</option>
      <option value="D-080" {% if ds_front == 'D-080' %}selected{% endif %}>D-080</option>
      <option value="D-106" {% if ds_front == 'D-106' %}selected{% endif %}>D-106</option>
      <option value="D-111" {% if ds_front == 'D-111' %}selected{% endif %}>D-111</option>
      <option value="D-125" {% if ds_front == 'D-125' %}selected{% endif %}>D-125</option>
      <option value="D-128" {% if ds_front == 'D-128' %}selected{% endif %}>D-128</option>
      <option value="D-129" {% if ds_front == 'D-129' %}selected{% endif %}>D-129</option>
      <option value="D-138" {% if ds_front == 'D-138' %}selected{% endif %}>D-138</option>
      <option value="D-140" {% if ds_front == 'D-140' %}selected{% endif %}>D-140</option>
      <option value="D-150" {% if ds_front == 'D-150' %}selected{% endif %}>D-150</option>
      <option value="D-157" {% if ds_front == 'D-157' %}selected{% endif %}>D-157</option>
      <option value="D-167" {% if ds_front == 'D-167' %}selected{% endif %}>D-167</option>
      <option value="D-168" {% if ds_front == 'D-168' %}selected{% endif %}>D-168</option>
      <option value="D-177" {% if ds_front == 'D-177' %}selected{% endif %}>D-177</option>
      <option value="D-195" {% if ds_front == 'D-195' %}selected{% endif %}>D-195</option>
      <option value="D-201" {% if ds_front == 'D-201' %}selected{% endif %}>D-201</option>
      <option value="D-212" {% if ds_front == 'D-212' %}selected{% endif %}>D-212</option>
      <option value="D-213" {% if ds_front == 'D-213' %}selected{% endif %}>D-213</option>
      <option value="D-218" {% if ds_front == 'D-218' %}selected{% endif %}>D-218</option>
      <option value="D-220" {% if ds_front == 'D-220' %}selected{% endif %}>D-220</option>
      <option value="D-222" {% if ds_front == 'D-222' %}selected{% endif %}>D-222</option>
      <option value="D-223" {% if ds_front == 'D-223' %}selected{% endif %}>D-223</option>
      <option value="D-229" {% if ds_front == 'D-229' %}selected{% endif %}>D-229</option>
      <option value="D-230" {% if ds_front == 'D-230' %}selected{% endif %}>D-230</option>
      <option value="D-231" {% if ds_front == 'D-231' %}selected{% endif %}>D-231</option>
      <option value="D-233" {% if ds_front == 'D-233' %}selected{% endif %}>D-233</option>
      <option value="D-234" {% if ds_front == 'D-234' %}selected{% endif %}>D-234</option>
      <option value="D-235" {% if ds_front == 'D-235' %}selected{% endif %}>D-235</option>
      <option value="D-236" {% if ds_front == 'D-236' %}selected{% endif %}>D-236</option>
      <option value="D-238" {% if ds_front == 'D-238' %}selected{% endif %}>D-238</option>
      <option value="D-240" {% if ds_front == 'D-240' %}selected{% endif %}>D-240</option>
      <option value="D-241" {% if ds_front == 'D-241' %}selected{% endif %}>D-241</option>
      <option value="D-242" {% if ds_front == 'D-242' %}selected{% endif %}>D-242</option>
      <option value="D-244" {% if ds_front == 'D-244' %}selected{% endif %}>D-244</option>
      <option value="D-246" {% if ds_front == 'D-246' %}selected{% endif %}>D-246</option>
      <option value="D-247" {% if ds_front == 'D-247' %}selected{% endif %}>D-247</option>
      <option value="D-248" {% if ds_front == 'D-248' %}selected{% endif %}>D-248</option>
      <option value="D-260" {% if ds_front == 'D-260' %}selected{% endif %}>D-260</option>
      <option value="D-266" {% if ds_front == 'D-266' %}selected{% endif %}>D-266</option>
      <option value="D-273" {% if ds_front == 'D-273' %}selected{% endif %}>D-273</option>
      <option value="D-274" {% if ds_front == 'D-274' %}selected{% endif %}>D-274</option>
      <option value="D-275" {% if ds_front == 'D-275' %}selected{% endif %}>D-275</option>
      <option value="D-280" {% if ds_front == 'D-280' %}selected{% endif %}>D-280</option>
      <option value="D-281" {% if ds_front == 'D-281' %}selected{% endif %}>D-281</option>
      <option value="D-286" {% if ds_front == 'D-286' %}selected{% endif %}>D-286</option>
      <option value="D-287" {% if ds_front == 'D-287' %}selected{% endif %}>D-287</option>
      <option value="D-288" {% if ds_front == 'D-288' %}selected{% endif %}>D-288</option>
      <option value="D-291" {% if ds_front == 'D-291' %}selected{% endif %}>D-291</option>
      <option value="D-292" {% if ds_front == 'D-292' %}selected{% endif %}>D-292</option>
      <option value="D-298" {% if ds_front == 'D-298' %}selected{% endif %}>D-298</option>
      <option value="D-299" {% if ds_front == 'D-299' %}selected{% endif %}>D-299</option>
      <option value="D-300" {% if ds_front == 'D-300' %}selected{% endif %}>D-300</option>
      <option value="D-301" {% if ds_front == 'D-301' %}selected{% endif %}>D-301</option>
      <option value="D-307" {% if ds_front == 'D-307' %}selected{% endif %}>D-307</option>
      <option value="D-309" {% if ds_front == 'D-309' %}selected{% endif %}>D-309</option>
      <option value="D-315" {% if ds_front == 'D-315' %}selected{% endif %}>D-315</option>
      <option value="D-317" {% if ds_front == 'D-317' %}selected{% endif %}>D-317</option>
      <option value="D-318" {% if ds_front == 'D-318' %}selected{% endif %}>D-318</option>
      <option value="D-322" {% if ds_front == 'D-322' %}selected{% endif %}>D-322</option>
      <option value="D-332" {% if ds_front == 'D-332' %}selected{% endif %}>D-332</option>
      <option value="D-334" {% if ds_front == 'D-334' %}selected{% endif %}>D-334</option>
      <option value="D-335" {% if ds_front == 'D-335' %}selected{% endif %}>D-335</option>
      <option value="D-337" {% if ds_front == 'D-337' %}selected{% endif %}>D-337</option>
      <option value="D-340" {% if ds_front == 'D-340' %}selected{% endif %}>D-340</option>
      <option value="D-341" {% if ds_front == 'D-341' %}selected{% endif %}>D-341</option>
      <option value="D-344" {% if ds_front == 'D-344' %}selected{% endif %}>D-344</option>
      <option value="D-346" {% if ds_front == 'D-346' %}selected{% endif %}>D-346</option>
      <option value="D-347" {% if ds_front == 'D-347' %}selected{% endif %}>D-347</option>
      <option value="D-348" {% if ds_front == 'D-348' %}selected{% endif %}>D-348</option>
      <option value="D-349" {% if ds_front == 'D-349' %}selected{% endif %}>D-349</option>
      <option value="D-352" {% if ds_front == 'D-352' %}selected{% endif %}>D-352</option>
      <option value="D-353" {% if ds_front == 'D-353' %}selected{% endif %}>D-353</option>
      <option value="D-354" {% if ds_front == 'D-354' %}selected{% endif %}>D-354</option>
      <option value="D-355" {% if ds_front == 'D-355' %}selected{% endif %}>D-355</option>
      <option value="D-358" {% if ds_front == 'D-358' %}selected{% endif %}>D-358</option>
      <option value="D-363" {% if ds_front == 'D-363' %}selected{% endif %}>D-363</option>
      <option value="D-364" {% if ds_front == 'D-364' %}selected{% endif %}>D-364</option>
      <option value="D-365" {% if ds_front == 'D-365' %}selected{% endif %}>D-365</option>
      <option value="D-366" {% if ds_front == 'D-366' %}selected{% endif %}>D-366</option>
      <option value="D-367" {% if ds_front == 'D-367' %}selected{% endif %}>D-367</option>
      <option value="D-368" {% if ds_front == 'D-368' %}selected{% endif %}>D-368</option>
      <option value="D-370" {% if ds_front == 'D-370' %}selected{% endif %}>D-370</option>
      <option value="D-372" {% if ds_front == 'D-372' %}selected{% endif %}>D-372</option>
      <option value="D-373" {% if ds_front == 'D-373' %}selected{% endif %}>D-373</option>
      <option value="D-374" {% if ds_front == 'D-374' %}selected{% endif %}>D-374</option>
      <option value="D-375" {% if ds_front == 'D-375' %}selected{% endif %}>D-375</option>
      <option value="D-376" {% if ds_front == 'D-376' %}selected{% endif %}>D-376</option>
      <option value="D-377" {% if ds_front == 'D-377' %}selected{% endif %}>D-377</option>
      <option value="D-378" {% if ds_front == 'D-378' %}selected{% endif %}>D-378</option>
      <option value="D-379" {% if ds_front == 'D-379' %}selected{% endif %}>D-379</option>
      <option value="D-380" {% if ds_front == 'D-380' %}selected{% endif %}>D-380</option>
      <option value="D-381" {% if ds_front == 'D-381' %}selected{% endif %}>D-381</option>
      <option value="D-382" {% if ds_front == 'D-382' %}selected{% endif %}>D-382</option>
      <option value="D-383" {% if ds_front == 'D-383' %}selected{% endif %}>D-383</option>
      <option value="D-384" {% if ds_front == 'D-384' %}selected{% endif %}>D-384</option>
      <option value="D-385" {% if ds_front == 'D-385' %}selected{% endif %}>D-385</option>
      <option value="D-386" {% if ds_front == 'D-386' %}selected{% endif %}>D-386</option>
      <option value="D-388" {% if ds_front == 'D-388' %}selected{% endif %}>D-388</option>
      <option value="D-390" {% if ds_front == 'D-390' %}selected{% endif %}>D-390</option>
      <option value="D-391" {% if ds_front == 'D-391' %}selected{% endif %}>D-391</option>
      <option value="D-392" {% if ds_front == 'D-392' %}selected{% endif %}>D-392</option>
      <option value="D-393" {% if ds_front == 'D-393' %}selected{% endif %}>D-393</option>
      <option value="D-394" {% if ds_front == 'D-394' %}selected{% endif %}>D-394</option>
      <option value="D-396" {% if ds_front == 'D-396' %}selected{% endif %}>D-396</option>
      <option value="D-397" {% if ds_front == 'D-397' %}selected{% endif %}>D-397</option>
      <option value="D-398" {% if ds_front == 'D-398' %}selected{% endif %}>D-398</option>
      <option value="D-399" {% if ds_front == 'D-399' %}selected{% endif %}>D-399</option>
      <option value="D-400" {% if ds_front == 'D-400' %}selected{% endif %}>D-400</option>
      <option value="D-401" {% if ds_front == 'D-401' %}selected{% endif %}>D-401</option>
      <option value="D-402" {% if ds_front == 'D-402' %}selected{% endif %}>D-402</option>
      <option value="D-403" {% if ds_front == 'D-403' %}selected{% endif %}>D-403</option>
      <option value="D-404" {% if ds_front == 'D-404' %}selected{% endif %}>D-404</option>
      <option value="D-405" {% if ds_front == 'D-405' %}selected{% endif %}>D-405</option>
    </select>
    </select>

    <label>カスタムプリントデータ(その他):</label>
    <input type="file" name="position_data_other">
    </div>

    <!-- ▼▼ プリント位置(その他) => 選択式に変更 ▼▼ -->
    <label>プリント位置(その他):</label>
    <select name="other_positions_selected">
      <option value="">選択してください</option>
      {% set o_pos = extracted_data['other_positions_selected'] if extracted_data['other_positions_selected'] else '' %}
      <option value="左袖：袖口" {% if o_pos == '左袖：袖口' %}selected{% endif %}>左袖：袖口</option>
      <option value="左袖：長袖中央" {% if o_pos == '左袖：長袖中央' %}selected{% endif %}>左袖：長袖中央</option>
      <option value="左袖：長袖肩口" {% if o_pos == '左袖：長袖肩口' %}selected{% endif %}>左袖：長袖肩口</option>
      <option value="左袖：長袖袖口" {% if o_pos == '左袖：長袖袖口' %}selected{% endif %}>左袖：長袖袖口</option>
      <option value="右袖：袖口" {% if o_pos == '右袖：袖口' %}selected{% endif %}>右袖：袖口</option>
      <option value="右袖：長袖中央" {% if o_pos == '右袖：長袖中央' %}selected{% endif %}>右袖：長袖中央</option>
      <option value="右袖：長袖肩口" {% if o_pos == '右袖：長袖肩口' %}selected{% endif %}>右袖：長袖肩口</option>
      <option value="右袖：長袖袖口" {% if o_pos == '右袖：長袖袖口' %}selected{% endif %}>右袖：長袖袖口</option>
    </select>


    <h3>背ネーム・背番号プリント</h3>
    <p class="instruction">※複数選択可能</p>
    <div class="checkbox-group">
      {% set bn_list = extracted_data['back_name_number_print'] if extracted_data['back_name_number_print'] else [] %}
      <label><input type="checkbox" name="back_name_number_print[]" value="ネーム&背番号セット" {% if 'ネーム&背番号セット' in bn_list %}checked{% endif %}> ネーム&背番号セット</label>
      <label><input type="checkbox" name="back_name_number_print[]" value="ネーム(大)" {% if 'ネーム(大)' in bn_list %}checked{% endif %}> ネーム(大)</label>
      <label><input type="checkbox" name="back_name_number_print[]" value="ネーム(小)" {% if 'ネーム(小)' in bn_list %}checked{% endif %}> ネーム(小)</label>
      <label><input type="checkbox" name="back_name_number_print[]" value="番号(大)" {% if '番号(大)' in bn_list %}checked{% endif %}> 番号(大)</label>
      <label><input type="checkbox" name="back_name_number_print[]" value="番号(小)" {% if '番号(小)' in bn_list %}checked{% endif %}> 番号(小)</label>
      <label><input type="checkbox" name="back_name_number_print[]" value="ネーム＆背番号を使わない" {% if 'ネーム＆背番号を使わない' in bn_list %}checked{% endif %}> ネーム＆背番号を使わない</label>
    </div>

    <!-- ▼▼ 背ネーム・背番号のカラー設定 ▼▼ -->
    <h3>背ネーム・背番号 カラー設定</h3>
    <p>「単色」または「フチ付き(2色)」を選択してください。</p>

    <!-- ラジオボタン：単色 or フチ付き -->
    <div class="radio-group" id="nameNumberColorType">
      {% set color_type = extracted_data['name_number_color_type']|default('single') %}
      <label>
        <input type="radio" name="name_number_color_type" value="single"
          {% if color_type == 'single' %}checked{% endif %}>
        単色
      </label>
      <label>
        <input type="radio" name="name_number_color_type" value="outline"
          {% if color_type == 'outline' %}checked{% endif %}>
        フチ付き(2色)
      </label>
    </div>

    <!-- ▼ 単色カラー ▼ -->
    <div id="singleColorSection"
         style="{% if color_type == 'outline' %}display:none{% else %}display:block{% endif %}">
      <label>単色カラー:</label>
      {% set single_c = extracted_data['single_color_choice'] %}
      <select name="single_color_choice">
        <option value="" {% if not single_c %}selected{% endif %}>選択してください</option>
        <option value="ホワイト" {% if single_c == 'ホワイト' %}selected{% endif %}>ホワイト</option>
        <option value="グレー" {% if single_c == 'グレー' %}selected{% endif %}>グレー</option>
        <option value="ネイビー" {% if single_c == 'ネイビー' %}selected{% endif %}>ネイビー</option>
        <option value="ブラック" {% if single_c == 'ブラック' %}selected{% endif %}>ブラック</option>
        <option value="ライトブルー" {% if single_c == 'ライトブルー' %}selected{% endif %}>ライトブルー</option>
        <option value="ブルー" {% if single_c == 'ブルー' %}selected{% endif %}>ブルー</option>
        <option value="イエロー" {% if single_c == 'イエロー' %}selected{% endif %}>イエロー</option>
        <option value="オレンジ" {% if single_c == 'オレンジ' %}selected{% endif %}>オレンジ</option>
        <option value="ピンク" {% if single_c == 'ピンク' %}selected{% endif %}>ピンク</option>
        <option value="ホットピンク" {% if single_c == 'ホットピンク' %}selected{% endif %}>ホットピンク</option>
        <option value="レッド" {% if single_c == 'レッド' %}selected{% endif %}>レッド</option>
        <option value="パープル" {% if single_c == 'パープル' %}selected{% endif %}>パープル</option>
        <option value="ライトグリーン" {% if single_c == 'ライトグリーン' %}selected{% endif %}>ライトグリーン</option>
        <option value="グリーン" {% if single_c == 'グリーン' %}selected{% endif %}>グリーン</option>
        <option value="シルバー" {% if single_c == 'シルバー' %}selected{% endif %}>シルバー</option>
        <option value="ゴールド" {% if single_c == 'ゴールド' %}selected{% endif %}>ゴールド</option>
        <option value="グリッターシルバー" {% if single_c == 'グリッターシルバー' %}selected{% endif %}>グリッターシルバー</option>
        <option value="グリッターゴールド" {% if single_c == 'グリッターゴールド' %}selected{% endif %}>グリッターゴールド</option>
        <option value="グリッターピンク" {% if single_c == 'グリッターピンク' %}selected{% endif %}>グリッターピンク</option>
      </select>
    </div>

    <!-- ▼ フチ付き(2色) ▼ -->
    <div id="outlineColorSection"
         style="{% if color_type == 'outline' %}display:block{% else %}display:none{% endif %}; margin-top:16px;">
      <label>タイプ (フチ付きデザイン):</label>
      {% set out_type = extracted_data['outline_type'] %}
      <select name="outline_type">
        <option value="" {% if not out_type %}selected{% endif %}>選択してください</option>
        <option value="FT-01" {% if out_type == 'FT-01' %}selected{% endif %}>FT-01</option>
        <option value="FT-02" {% if out_type == 'FT-02' %}selected{% endif %}>FT-02</option>
      </select>

      <label>文字色:</label>
      {% set txt_c = extracted_data['outline_text_color'] %}
      <select name="outline_text_color">
        <option value="" {% if not txt_c %}selected{% endif %}>選択してください</option>
        <option value="ホワイト" {% if txt_c == 'ホワイト' %}selected{% endif %}>ホワイト</option>
        <option value="グレー" {% if txt_c == 'グレー' %}selected{% endif %}>グレー</option>
        <option value="ネイビー" {% if txt_c == 'ネイビー' %}selected{% endif %}>ネイビー</option>
        <option value="ブラック" {% if txt_c == 'ブラック' %}selected{% endif %}>ブラック</option>
        <option value="ライトブルー" {% if txt_c == 'ライトブルー' %}selected{% endif %}>ライトブルー</option>
        <option value="ブルー" {% if txt_c == 'ブルー' %}selected{% endif %}>ブルー</option>
        <option value="イエロー" {% if txt_c == 'イエロー' %}selected{% endif %}>イエロー</option>
        <option value="オレンジ" {% if txt_c == 'オレンジ' %}selected{% endif %}>オレンジ</option>
        <option value="ピンク" {% if txt_c == 'ピンク' %}selected{% endif %}>ピンク</option>
        <option value="ホットピンク" {% if txt_c == 'ホットピンク' %}selected{% endif %}>ホットピンク</option>
        <option value="レッド" {% if txt_c == 'レッド' %}selected{% endif %}>レッド</option>
        <option value="パープル" {% if txt_c == 'パープル' %}selected{% endif %}>パープル</option>
        <option value="ライトグリーン" {% if txt_c == 'ライトグリーン' %}selected{% endif %}>ライトグリーン</option>
        <option value="グリーン" {% if txt_c == 'グリーン' %}selected{% endif %}>グリーン</option>
        <option value="シルバー" {% if txt_c == 'シルバー' %}selected{% endif %}>シルバー</option>
        <option value="ゴールド" {% if txt_c == 'ゴールド' %}selected{% endif %}>ゴールド</option>
        <option value="グリッターシルバー" {% if txt_c == 'グリッターシルバー' %}selected{% endif %}>グリッターシルバー</option>
        <option value="グリッターゴールド" {% if txt_c == 'グリッターゴールド' %}selected{% endif %}>グリッターゴールド</option>
        <option value="グリッターピンク" {% if txt_c == 'グリッターピンク' %}selected{% endif %}>グリッターピンク</option>
      </select>

      <label>フチ色:</label>
      {% set edge_c = extracted_data['outline_edge_color'] %}
      <select name="outline_edge_color">
        <option value="" {% if not edge_c %}selected{% endif %}>選択してください</option>
        <option value="ホワイト" {% if edge_c == 'ホワイト' %}selected{% endif %}>ホワイト</option>
        <option value="グレー" {% if edge_c == 'グレー' %}selected{% endif %}>グレー</option>
        <option value="ネイビー" {% if edge_c == 'ネイビー' %}selected{% endif %}>ネイビー</option>
        <option value="ブラック" {% if edge_c == 'ブラック' %}selected{% endif %}>ブラック</option>
        <option value="ライトブルー" {% if edge_c == 'ライトブルー' %}selected{% endif %}>ライトブルー</option>
        <option value="ブルー" {% if edge_c == 'ブルー' %}selected{% endif %}>ブルー</option>
        <option value="イエロー" {% if edge_c == 'イエロー' %}selected{% endif %}>イエロー</option>
        <option value="オレンジ" {% if edge_c == 'オレンジ' %}selected{% endif %}>オレンジ</option>
        <option value="ピンク" {% if edge_c == 'ピンク' %}selected{% endif %}>ピンク</option>
        <option value="ホットピンク" {% if edge_c == 'ホットピンク' %}selected{% endif %}>ホットピンク</option>
        <option value="レッド" {% if edge_c == 'レッド' %}selected{% endif %}>レッド</option>
        <option value="パープル" {% if edge_c == 'パープル' %}selected{% endif %}>パープル</option>
        <option value="ライトグリーン" {% if edge_c == 'ライトグリーン' %}selected{% endif %}>ライトグリーン</option>
        <option value="グリーン" {% if edge_c == 'グリーン' %}selected{% endif %}>グリーン</option>
        <option value="シルバー" {% if edge_c == 'シルバー' %}selected{% endif %}>シルバー</option>
        <option value="ゴールド" {% if edge_c == 'ゴールド' %}selected{% endif %}>ゴールド</option>
        <option value="グリッターシルバー" {% if edge_c == 'グリッターシルバー' %}selected{% endif %}>グリッターシルバー</option>
        <option value="グリッターゴールド" {% if edge_c == 'グリッターゴールド' %}selected{% endif %}>グリッターゴールド</option>
        <option value="グリッターピンク" {% if edge_c == 'グリッターピンク' %}selected{% endif %}>グリッターピンク</option>
      </select>
    </div>

    <script>
    // 「単色」か「フチ付き(2色)」かで表示・非表示を切り替え
    const radioGroup = document.getElementById('nameNumberColorType');
    const singleSec = document.getElementById('singleColorSection');
    const outlineSec = document.getElementById('outlineColorSection');

    radioGroup.addEventListener('change', function(e) {
      if (e.target.value === 'single') {
        singleSec.style.display = 'block';
        outlineSec.style.display = 'none';
      } else {
        singleSec.style.display = 'none';
        outlineSec.style.display = 'block';
      }
    });

    // プリントカラー選択を最大4つまでに制限
    function limitSelection(selectElem, maxCount) {
      const selectedOptions = Array.from(selectElem.selectedOptions);
      if (selectedOptions.length > maxCount) {
        selectedOptions[selectedOptions.length - 1].selected = false;
        alert("同時に選択できるカラーは最大 " + maxCount + " つまでです。");
      }
    }

    // 郵便番号から住所を取得 (Zipcloud)
    function fetchAddress() {
      const zip = document.getElementById('delivery_zip').value.replace('-', '').trim();
      if (!zip) {
        alert('郵便番号を入力してください');
        return;
      }
      const url = 'https://zipcloud.ibsnet.co.jp/api/search?zipcode=' + encodeURIComponent(zip);
      fetch(url)
        .then(res => res.json())
        .then(data => {
          if (data.status === 200 && data.results && data.results.length > 0) {
            const result = data.results[0];
            const address = result.address1 + result.address2 + result.address3;
            document.getElementById('delivery_address').value = address;
          } else {
            alert('住所を取得できませんでした。郵便番号をご確認ください。');
          }
        })
        .catch(err => {
          console.error(err);
          alert('エラーが発生しました。');
        });
    }
    </script>

    <button type="submit">送信</button>
  </form>
</body>
</html>
"""

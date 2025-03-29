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
    <input type="date" name="application_date">

    <label>配達日:</label>
    <input type="date" name="delivery_date">

    <label>使用日:</label>
    <input type="date" name="use_date">

    <label>利用する学割特典:</label>
    <select name="discount_option">
      <option value="早割">早割</option>
      <option value="タダ割">タダ割</option>
      <option value="いっしょ割り">いっしょ割り</option>
    </select>

    <label>学校名:</label>
    <input type="text" name="school_name">

    <label>LINEアカウント名:</label>
    <input type="text" name="line_account">

    <label>団体名:</label>
    <input type="text" name="group_name">

    <label>学校住所:</label>
    <input type="text" name="school_address">

    <label>学校TEL:</label>
    <input type="text" name="school_tel">

    <label>担任名:</label>
    <input type="text" name="teacher_name">

    <label>担任携帯:</label>
    <input type="text" name="teacher_tel">

    <label>担任メール:</label>
    <input type="email" name="teacher_email">

    <label>代表者:</label>
    <input type="text" name="representative">

    <label>代表者TEL:</label>
    <input type="text" name="rep_tel">

    <label>代表者メール:</label>
    <input type="email" name="rep_email">

    <!-- ▼▼ ここから「お届け先」追加 ▼▼ -->
    <label>お届け先 郵便番号:</label>
    <input type="text" id="delivery_zip" placeholder="例: 1000001">
    <button type="button" onclick="fetchAddress()">住所を自動入力</button>
    <div>※半角数字で入力、ハイフン不要</div>

    <label>お届け先住所:</label>
    <input type="text" id="delivery_address" name="delivery_address" placeholder="都道府県～町域まで自動入力">

    <label>建物・部屋番号 (任意):</label>
    <input type="text" id="delivery_address2" name="delivery_address2" placeholder="建物名など">
    <!-- ▼▼ 「お届け先」ここまで ▼▼ -->


    <label>デザイン確認方法:</label>
    <select name="design_confirm">
      <option value="LINE代表者">LINE代表者</option>
      <option value="LINEご担任(保護者)">LINEご担任(保護者)</option>
      <option value="メール代表者">メール代表者</option>
      <option value="メールご担任(保護者)">メールご担任(保護者)</option>
    </select>

    <label>お支払い方法:</label>
    <select name="payment_method">
      <option value="代金引換(ヤマト運輸/現金のみ)">代金引換(ヤマト運輸/現金のみ)</option>
      <option value="背中払い(コンビニ/郵便振替)">背中払い(コンビニ/郵便振替)</option>
      <option value="背中払い(銀行振込)">背中払い(銀行振込)</option>
      <option value="先払い(銀行振込)">先払い(銀行振込)</option>
    </select>

    <label>商品名:</label>
    <select name="product_name">
      <option value="ドライTシャツ">ドライTシャツ</option>
      <option value="ヘビーウェイトTシャツ">ヘビーウェイトTシャツ</option>
      <option value="ドライポロシャツ">ドライポロシャツ</option>
      <option value="ドライメッシュビブス">ドライメッシュビブス</option>
      <option value="ドライベースボールシャツ">ドライベースボールシャツ</option>
      <option value="ドライロングスリープTシャツ">ドライロングスリープTシャツ</option>
      <option value="ドライハーフパンツ">ドライハーフパンツ</option>
      <option value="ヘビーウェイトロングスリープTシャツ">ヘビーウェイトロングスリープTシャツ</option>
      <option value="クルーネックライトトレーナー">クルーネックライトトレーナー</option>
      <option value="フーデッドライトパーカー">フーデッドライトパーカー</option>
      <option value="スタンダードトレーナー">スタンダードトレーナー</option>
      <option value="スタンダードWフードパーカー">スタンダードWフードパーカー</option>
      <option value="ジップアップライトパーカー">ジップアップライトパーカー</option>
    </select>

    <label>商品カラー:</label>
    <input type="text" name="product_color">

    <label>サイズ(SS):</label>
    <input type="number" name="size_ss">
    <label>サイズ(S):</label>
    <input type="number" name="size_s">
    <label>サイズ(M):</label>
    <input type="number" name="size_m">
    <label>サイズ(L):</label>
    <input type="number" name="size_l">
    <label>サイズ(LL):</label>
    <input type="number" name="size_ll">
    <label>サイズ(LLL):</label>
    <input type="number" name="size_lll">


    <!-- ▼▼ 前面プリント ▼▼ -->
    <h3>プリント位置: 前</h3>
    <div class="radio-group">
      <label>
        <input type="radio" name="print_size_front" value="おまかせ (最大:横28cm x 縦35cm以内)" checked>
        おまかせ (最大:横28cm x 縦35cm以内)
      </label>
      <label>
        <input type="radio" name="print_size_front" value="custom">
        ヨコcm x タテcmくらい(入力する):
      </label>
    </div>
    <input type="text" name="print_size_front_custom" placeholder="例: 20cm x 15cm">

    <!-- ▼▼ プリントカラー(前) - シンプルな選択式 (複数選択) ▼▼ -->
    <label>プリントカラー(前):</label>
    <select name="print_color_front[]" multiple onchange="limitSelection(this, 4)">
      <option value="">選択してください</option>
      <option value="ホワイト">ホワイト</option>
      <option value="ライトグレー">ライトグレー</option>
      <option value="ダークグレー">ダークグレー</option>
      <option value="ブラック">ブラック</option>
      <option value="サックス">サックス</option>
      <option value="ブルー">ブルー</option>
      <option value="ネイビー">ネイビー</option>
      <option value="ライトピンク">ライトピンク</option>
      <option value="ローズピンク">ローズピンク</option>
      <option value="ホットピンク">ホットピンク</option>
      <option value="レッド">レッド</option>
      <option value="ワインレッド">ワインレッド</option>
      <option value="ミントグリーン">ミントグリーン</option>
      <option value="エメラルドグリーン">エメラルドグリーン</option>
      <option value="パステルイエロー">パステルイエロー</option>
      <option value="イエロー">イエロー</option>
      <option value="ゴールドイエロー">ゴールドイエロー</option>
      <option value="オレンジ">オレンジ</option>
      <option value="イエローグリーン">イエローグリーン</option>
      <option value="グリーン">グリーン</option>
      <option value="ダークグリーン">ダークグリーン</option>
      <option value="ライトパープル">ライトパープル</option>
      <option value="パープル">パープル</option>
      <option value="クリーム">クリーム</option>
      <option value="ライトブラウン">ライトブラウン</option>
      <option value="ダークブラウン">ダークブラウン</option>
      <option value="シルバー">シルバー</option>
      <option value="ゴールド">ゴールド</option>
      <option value="グリッターシルバー">グリッターシルバー</option>
      <option value="グリッターゴールド">グリッターゴールド</option>
      <option value="グリッターブラック">グリッターブラック</option>
      <option value="グリッターイエロー">グリッターイエロー</option>
      <option value="グリッターピンク">グリッターピンク</option>
      <option value="グリッターレッド">グリッターレッド</option>
      <option value="グリッターグリーン">グリッターグリーン</option>
      <option value="グリッターブルー">グリッターブルー</option>
      <option value="グリッターパープル">グリッターパープル</option>
      <option value="蛍光オレンジ">蛍光オレンジ</option>
      <option value="蛍光ピンク">蛍光ピンク</option>
      <option value="蛍光グリーン">蛍光グリーン</option>
      <option value="フルカラー(小)">フルカラー(小)</option>
      <option value="フルカラー(中)">フルカラー(中)</option>
      <option value="フルカラー(大)">フルカラー(大)</option>
    </select>

    <label>フォントNo.(前):</label>
    <select name="font_no_front">
      <option value="">選択してください</option>
      <option value="E-01">E-01</option>
      <option value="E-02">E-02</option>
      <option value="E-03">E-03</option>
      <option value="E-05">E-05</option>
      <option value="E-06">E-06</option>
      <option value="E-09">E-09</option>
      <option value="E-10">E-10</option>
      <option value="E-13">E-13</option>
      <option value="E-14">E-14</option>
      <option value="E-15">E-15</option>
      <option value="E-16">E-16</option>
      <option value="E-17">E-17</option>
      <option value="E-18">E-18</option>
      <option value="E-19">E-19</option>
      <option value="E-20">E-20</option>
      <option value="E-21">E-21</option>
      <option value="E-22">E-22</option>
      <option value="E-23">E-23</option>
      <option value="E-24">E-24</option>
      <option value="E-25">E-25</option>
      <option value="E-26">E-26</option>
      <option value="E-27">E-27</option>
      <option value="E-28">E-28</option>
      <option value="E-29">E-29</option>
      <option value="E-30">E-30</option>
      <option value="E-31">E-31</option>
      <option value="E-32">E-32</option>
      <option value="E-33">E-33</option>
      <option value="E-34">E-34</option>
      <option value="E-35">E-35</option>
      <option value="E-37">E-37</option>
      <option value="E-38">E-38</option>
      <option value="E-40">E-40</option>
      <option value="E-41">E-41</option>
      <option value="E-42">E-42</option>
      <option value="E-43">E-43</option>
      <option value="E-44">E-44</option>
      <option value="E-45">E-45</option>
      <option value="E-46">E-46</option>
      <option value="E-47">E-47</option>
      <option value="E-50">E-50</option>
      <option value="E-51">E-51</option>
      <option value="E-52">E-52</option>
      <option value="E-53">E-53</option>
      <option value="E-54">E-54</option>
      <option value="E-55">E-55</option>
      <option value="E-56">E-56</option>
      <option value="E-57">E-57</option>
    </select>

    <label>デザインサンプル(前):</label>
    <select name="design_sample_front">
      <option value="">選択してください</option>
      <option value="D-008">D-008</option>
      <option value="D-009">D-009</option>
      <option value="D-012">D-012</option>
      <option value="D-013">D-013</option>
      <option value="D-014">D-014</option>
      <option value="D-015">D-015</option>
      <option value="D-027">D-027</option>
      <option value="D-028">D-028</option>
      <option value="D-029">D-029</option>
      <option value="D-030">D-030</option>
      <option value="D-039">D-039</option>
      <option value="D-040">D-040</option>
      <option value="D-041">D-041</option>
      <option value="D-042">D-042</option>
      <option value="D-051">D-051</option>
      <option value="D-068">D-068</option>
      <option value="D-080">D-080</option>
      <option value="D-106">D-106</option>
      <option value="D-111">D-111</option>
      <option value="D-125">D-125</option>
      <option value="D-128">D-128</option>
      <option value="D-129">D-129</option>
      <option value="D-138">D-138</option>
      <option value="D-140">D-140</option>
      <option value="D-150">D-150</option>
      <option value="D-157">D-157</option>
      <option value="D-167">D-167</option>
      <option value="D-168">D-168</option>
      <option value="D-177">D-177</option>
      <option value="D-195">D-195</option>
      <option value="D-201">D-201</option>
      <option value="D-212">D-212</option>
      <option value="D-213">D-213</option>
      <option value="D-218">D-218</option>
      <option value="D-220">D-220</option>
      <option value="D-222">D-222</option>
      <option value="D-223">D-223</option>
      <option value="D-229">D-229</option>
      <option value="D-230">D-230</option>
      <option value="D-231">D-231</option>
      <option value="D-233">D-233</option>
      <option value="D-234">D-234</option>
      <option value="D-235">D-235</option>
      <option value="D-236">D-236</option>
      <option value="D-238">D-238</option>
      <option value="D-240">D-240</option>
      <option value="D-241">D-241</option>
      <option value="D-242">D-242</option>
      <option value="D-244">D-244</option>
      <option value="D-246">D-246</option>
      <option value="D-247">D-247</option>
      <option value="D-248">D-248</option>
      <option value="D-260">D-260</option>
      <option value="D-266">D-266</option>
      <option value="D-273">D-273</option>
      <option value="D-274">D-274</option>
      <option value="D-275">D-275</option>
      <option value="D-280">D-280</option>
      <option value="D-281">D-281</option>
      <option value="D-286">D-286</option>
      <option value="D-287">D-287</option>
      <option value="D-288">D-288</option>
      <option value="D-291">D-291</option>
      <option value="D-292">D-292</option>
      <option value="D-298">D-298</option>
      <option value="D-299">D-299</option>
      <option value="D-300">D-300</option>
      <option value="D-301">D-301</option>
      <option value="D-307">D-307</option>
      <option value="D-309">D-309</option>
      <option value="D-315">D-315</option>
      <option value="D-317">D-317</option>
      <option value="D-318">D-318</option>
      <option value="D-322">D-322</option>
      <option value="D-332">D-332</option>
      <option value="D-334">D-334</option>
      <option value="D-335">D-335</option>
      <option value="D-337">D-337</option>
      <option value="D-340">D-340</option>
      <option value="D-341">D-341</option>
      <option value="D-344">D-344</option>
      <option value="D-346">D-346</option>
      <option value="D-347">D-347</option>
      <option value="D-348">D-348</option>
      <option value="D-349">D-349</option>
      <option value="D-352">D-352</option>
      <option value="D-353">D-353</option>
      <option value="D-354">D-354</option>
      <option value="D-355">D-355</option>
      <option value="D-358">D-358</option>
      <option value="D-363">D-363</option>
      <option value="D-364">D-364</option>
      <option value="D-365">D-365</option>
      <option value="D-366">D-366</option>
      <option value="D-367">D-367</option>
      <option value="D-368">D-368</option>
      <option value="D-370">D-370</option>
      <option value="D-372">D-372</option>
      <option value="D-373">D-373</option>
      <option value="D-374">D-374</option>
      <option value="D-375">D-375</option>
      <option value="D-376">D-376</option>
      <option value="D-377">D-377</option>
      <option value="D-378">D-378</option>
      <option value="D-379">D-379</option>
      <option value="D-380">D-380</option>
      <option value="D-381">D-381</option>
      <option value="D-382">D-382</option>
      <option value="D-383">D-383</option>
      <option value="D-384">D-384</option>
      <option value="D-385">D-385</option>
      <option value="D-386">D-386</option>
      <option value="D-388">D-388</option>
      <option value="D-390">D-390</option>
      <option value="D-391">D-391</option>
      <option value="D-392">D-392</option>
      <option value="D-393">D-393</option>
      <option value="D-394">D-394</option>
      <option value="D-396">D-396</option>
      <option value="D-397">D-397</option>
      <option value="D-398">D-398</option>
      <option value="D-399">D-399</option>
      <option value="D-400">D-400</option>
      <option value="D-401">D-401</option>
      <option value="D-402">D-402</option>
      <option value="D-403">D-403</option>
      <option value="D-404">D-404</option>
      <option value="D-405">D-405</option>
    </select>

    <label>カスタムプリントデータ(前) (画像アップロード):</label>
    <input type="file" name="position_data_front">
    </div>

    <!-- ▼▼ プリント位置(前) => 選択式に変更 ▼▼ -->
    <label>プリント位置(前):</label>
    <select name="front_positions_selected">
      <option value="">選択してください</option>
      <option value="左胸">左胸</option>
      <option value="右胸">右胸</option>
      <option value="中央">中央</option>
      <option value="左下">左下</option>
      <option value="中央(下)">中央(下)</option>
      <option value="右下">右下</option>
    </select>


    <!-- ▼▼ 背面プリント ▼▼ -->
    <h3>プリント位置: 背中</h3>
    <div class="radio-group">
      <label>
        <input type="radio" name="print_size_back" value="おまかせ (最大:横28cm x 縦35cm以内)" checked>
        おまかせ (最大:横28cm x 縦35cm以内)
      </label>
      <label>
        <input type="radio" name="print_size_back" value="custom">
        ヨコcm x タテcmくらい(入力する):
      </label>
    </div>
    <input type="text" name="print_size_back_custom" placeholder="例: 20cm x 15cm">

    <!-- ▼▼ プリントカラー(背中) - シンプルな選択式 ▼▼ -->
    <label>プリントカラー(背中):</label>
    <select name="print_color_front[]" multiple onchange="limitSelection(this, 4)">
      <option value="">選択してください</option>
      <option value="ホワイト">ホワイト</option>
      <option value="ライトグレー">ライトグレー</option>
      <option value="ダークグレー">ダークグレー</option>
      <option value="ブラック">ブラック</option>
      <option value="サックス">サックス</option>
      <option value="ブルー">ブルー</option>
      <option value="ネイビー">ネイビー</option>
      <option value="ライトピンク">ライトピンク</option>
      <option value="ローズピンク">ローズピンク</option>
      <option value="ホットピンク">ホットピンク</option>
      <option value="レッド">レッド</option>
      <option value="ワインレッド">ワインレッド</option>
      <option value="ミントグリーン">ミントグリーン</option>
      <option value="エメラルドグリーン">エメラルドグリーン</option>
      <option value="パステルイエロー">パステルイエロー</option>
      <option value="イエロー">イエロー</option>
      <option value="ゴールドイエロー">ゴールドイエロー</option>
      <option value="オレンジ">オレンジ</option>
      <option value="イエローグリーン">イエローグリーン</option>
      <option value="グリーン">グリーン</option>
      <option value="ダークグリーン">ダークグリーン</option>
      <option value="ライトパープル">ライトパープル</option>
      <option value="パープル">パープル</option>
      <option value="クリーム">クリーム</option>
      <option value="ライトブラウン">ライトブラウン</option>
      <option value="ダークブラウン">ダークブラウン</option>
      <option value="シルバー">シルバー</option>
      <option value="ゴールド">ゴールド</option>
      <option value="グリッターシルバー">グリッターシルバー</option>
      <option value="グリッターゴールド">グリッターゴールド</option>
      <option value="グリッターブラック">グリッターブラック</option>
      <option value="グリッターイエロー">グリッターイエロー</option>
      <option value="グリッターピンク">グリッターピンク</option>
      <option value="グリッターレッド">グリッターレッド</option>
      <option value="グリッターグリーン">グリッターグリーン</option>
      <option value="グリッターブルー">グリッターブルー</option>
      <option value="グリッターパープル">グリッターパープル</option>
      <option value="蛍光オレンジ">蛍光オレンジ</option>
      <option value="蛍光ピンク">蛍光ピンク</option>
      <option value="蛍光グリーン">蛍光グリーン</option>
      <option value="フルカラー(小)">フルカラー(小)</option>
      <option value="フルカラー(中)">フルカラー(中)</option>
      <option value="フルカラー(大)">フルカラー(大)</option>
    </select>

    <label>フォントNo.(背中):</label>
    <select name="font_no_back">
      <option value="">選択してください</option>
      <option value="E-01">E-01</option>
      <option value="E-02">E-02</option>
      <option value="E-03">E-03</option>
      <option value="E-05">E-05</option>
      <option value="E-06">E-06</option>
      <option value="E-09">E-09</option>
      <option value="E-10">E-10</option>
      <option value="E-13">E-13</option>
      <option value="E-14">E-14</option>
      <option value="E-15">E-15</option>
      <option value="E-16">E-16</option>
      <option value="E-17">E-17</option>
      <option value="E-18">E-18</option>
      <option value="E-19">E-19</option>
      <option value="E-20">E-20</option>
      <option value="E-21">E-21</option>
      <option value="E-22">E-22</option>
      <option value="E-23">E-23</option>
      <option value="E-24">E-24</option>
      <option value="E-25">E-25</option>
      <option value="E-26">E-26</option>
      <option value="E-27">E-27</option>
      <option value="E-28">E-28</option>
      <option value="E-29">E-29</option>
      <option value="E-30">E-30</option>
      <option value="E-31">E-31</option>
      <option value="E-32">E-32</option>
      <option value="E-33">E-33</option>
      <option value="E-34">E-34</option>
      <option value="E-35">E-35</option>
      <option value="E-37">E-37</option>
      <option value="E-38">E-38</option>
      <option value="E-40">E-40</option>
      <option value="E-41">E-41</option>
      <option value="E-42">E-42</option>
      <option value="E-43">E-43</option>
      <option value="E-44">E-44</option>
      <option value="E-45">E-45</option>
      <option value="E-46">E-46</option>
      <option value="E-47">E-47</option>
      <option value="E-50">E-50</option>
      <option value="E-51">E-51</option>
      <option value="E-52">E-52</option>
      <option value="E-53">E-53</option>
      <option value="E-54">E-54</option>
      <option value="E-55">E-55</option>
      <option value="E-56">E-56</option>
      <option value="E-57">E-57</option>
    </select>

    <label>デザインサンプル(背中):</label>
    <select name="design_sample_back">
      <option value="">選択してください</option>
      <option value="D-008">D-008</option>
      <option value="D-009">D-009</option>
      <option value="D-012">D-012</option>
      <option value="D-013">D-013</option>
      <option value="D-014">D-014</option>
      <option value="D-015">D-015</option>
      <option value="D-027">D-027</option>
      <option value="D-028">D-028</option>
      <option value="D-029">D-029</option>
      <option value="D-030">D-030</option>
      <option value="D-039">D-039</option>
      <option value="D-040">D-040</option>
      <option value="D-041">D-041</option>
      <option value="D-042">D-042</option>
      <option value="D-051">D-051</option>
      <option value="D-068">D-068</option>
      <option value="D-080">D-080</option>
      <option value="D-106">D-106</option>
      <option value="D-111">D-111</option>
      <option value="D-125">D-125</option>
      <option value="D-128">D-128</option>
      <option value="D-129">D-129</option>
      <option value="D-138">D-138</option>
      <option value="D-140">D-140</option>
      <option value="D-150">D-150</option>
      <option value="D-157">D-157</option>
      <option value="D-167">D-167</option>
      <option value="D-168">D-168</option>
      <option value="D-177">D-177</option>
      <option value="D-195">D-195</option>
      <option value="D-201">D-201</option>
      <option value="D-212">D-212</option>
      <option value="D-213">D-213</option>
      <option value="D-218">D-218</option>
      <option value="D-220">D-220</option>
      <option value="D-222">D-222</option>
      <option value="D-223">D-223</option>
      <option value="D-229">D-229</option>
      <option value="D-230">D-230</option>
      <option value="D-231">D-231</option>
      <option value="D-233">D-233</option>
      <option value="D-234">D-234</option>
      <option value="D-235">D-235</option>
      <option value="D-236">D-236</option>
      <option value="D-238">D-238</option>
      <option value="D-240">D-240</option>
      <option value="D-241">D-241</option>
      <option value="D-242">D-242</option>
      <option value="D-244">D-244</option>
      <option value="D-246">D-246</option>
      <option value="D-247">D-247</option>
      <option value="D-248">D-248</option>
      <option value="D-260">D-260</option>
      <option value="D-266">D-266</option>
      <option value="D-273">D-273</option>
      <option value="D-274">D-274</option>
      <option value="D-275">D-275</option>
      <option value="D-280">D-280</option>
      <option value="D-281">D-281</option>
      <option value="D-286">D-286</option>
      <option value="D-287">D-287</option>
      <option value="D-288">D-288</option>
      <option value="D-291">D-291</option>
      <option value="D-292">D-292</option>
      <option value="D-298">D-298</option>
      <option value="D-299">D-299</option>
      <option value="D-300">D-300</option>
      <option value="D-301">D-301</option>
      <option value="D-307">D-307</option>
      <option value="D-309">D-309</option>
      <option value="D-315">D-315</option>
      <option value="D-317">D-317</option>
      <option value="D-318">D-318</option>
      <option value="D-322">D-322</option>
      <option value="D-332">D-332</option>
      <option value="D-334">D-334</option>
      <option value="D-335">D-335</option>
      <option value="D-337">D-337</option>
      <option value="D-340">D-340</option>
      <option value="D-341">D-341</option>
      <option value="D-344">D-344</option>
      <option value="D-346">D-346</option>
      <option value="D-347">D-347</option>
      <option value="D-348">D-348</option>
      <option value="D-349">D-349</option>
      <option value="D-352">D-352</option>
      <option value="D-353">D-353</option>
      <option value="D-354">D-354</option>
      <option value="D-355">D-355</option>
      <option value="D-358">D-358</option>
      <option value="D-363">D-363</option>
      <option value="D-364">D-364</option>
      <option value="D-365">D-365</option>
      <option value="D-366">D-366</option>
      <option value="D-367">D-367</option>
      <option value="D-368">D-368</option>
      <option value="D-370">D-370</option>
      <option value="D-372">D-372</option>
      <option value="D-373">D-373</option>
      <option value="D-374">D-374</option>
      <option value="D-375">D-375</option>
      <option value="D-376">D-376</option>
      <option value="D-377">D-377</option>
      <option value="D-378">D-378</option>
      <option value="D-379">D-379</option>
      <option value="D-380">D-380</option>
      <option value="D-381">D-381</option>
      <option value="D-382">D-382</option>
      <option value="D-383">D-383</option>
      <option value="D-384">D-384</option>
      <option value="D-385">D-385</option>
      <option value="D-386">D-386</option>
      <option value="D-388">D-388</option>
      <option value="D-390">D-390</option>
      <option value="D-391">D-391</option>
      <option value="D-392">D-392</option>
      <option value="D-393">D-393</option>
      <option value="D-394">D-394</option>
      <option value="D-396">D-396</option>
      <option value="D-397">D-397</option>
      <option value="D-398">D-398</option>
      <option value="D-399">D-399</option>
      <option value="D-400">D-400</option>
      <option value="D-401">D-401</option>
      <option value="D-402">D-402</option>
      <option value="D-403">D-403</option>
      <option value="D-404">D-404</option>
      <option value="D-405">D-405</option>
    </select>
    </select>

    <label>カスタムプリントデータ(背中) (画像アップロード):</label>
    <input type="file" name="position_data_back">
    </div>

    <!-- ▼▼ プリント位置(背中) => 選択式に変更 ▼▼ -->
    <label>プリント位置(背中):</label>
    <select name="back_positions_selected">
      <option value="">選択してください</option>
      <option value="首下">首下</option>
      <option value="中央">中央</option>
      <option value="左下">左下</option>
      <option value="中央(下)">中央(下)</option>
      <option value="右下">右下</option>
    </select>


    <!-- ▼▼ その他プリント ▼▼ -->
    <h3>プリント位置: その他</h3>
    <div class="radio-group">
      <label>
        <input type="radio" name="print_size_other" value="おまかせ (最大:横28cm x 縦35cm以内)" checked>
        おまかせ (最大:横28cm x 縦35cm以内)
      </label>
      <label>
        <input type="radio" name="print_size_other" value="custom">
        ヨコcm x タテcmくらい(入力する):
      </label>
    </div>
    <input type="text" name="print_size_other_custom" placeholder="例: 20cm x 15cm">

    <!-- ▼▼ プリントカラー(その他) - シンプルな選択式 (複数選択) ▼▼ -->
    <label>プリントカラー(その他):</label>
    <select name="print_color_front[]" multiple onchange="limitSelection(this, 4)">
      <option value="">選択してください</option>
      <option value="ホワイト">ホワイト</option>
      <option value="ライトグレー">ライトグレー</option>
      <option value="ダークグレー">ダークグレー</option>
      <option value="ブラック">ブラック</option>
      <option value="サックス">サックス</option>
      <option value="ブルー">ブルー</option>
      <option value="ネイビー">ネイビー</option>
      <option value="ライトピンク">ライトピンク</option>
      <option value="ローズピンク">ローズピンク</option>
      <option value="ホットピンク">ホットピンク</option>
      <option value="レッド">レッド</option>
      <option value="ワインレッド">ワインレッド</option>
      <option value="ミントグリーン">ミントグリーン</option>
      <option value="エメラルドグリーン">エメラルドグリーン</option>
      <option value="パステルイエロー">パステルイエロー</option>
      <option value="イエロー">イエロー</option>
      <option value="ゴールドイエロー">ゴールドイエロー</option>
      <option value="オレンジ">オレンジ</option>
      <option value="イエローグリーン">イエローグリーン</option>
      <option value="グリーン">グリーン</option>
      <option value="ダークグリーン">ダークグリーン</option>
      <option value="ライトパープル">ライトパープル</option>
      <option value="パープル">パープル</option>
      <option value="クリーム">クリーム</option>
      <option value="ライトブラウン">ライトブラウン</option>
      <option value="ダークブラウン">ダークブラウン</option>
      <option value="シルバー">シルバー</option>
      <option value="ゴールド">ゴールド</option>
      <option value="グリッターシルバー">グリッターシルバー</option>
      <option value="グリッターゴールド">グリッターゴールド</option>
      <option value="グリッターブラック">グリッターブラック</option>
      <option value="グリッターイエロー">グリッターイエロー</option>
      <option value="グリッターピンク">グリッターピンク</option>
      <option value="グリッターレッド">グリッターレッド</option>
      <option value="グリッターグリーン">グリッターグリーン</option>
      <option value="グリッターブルー">グリッターブルー</option>
      <option value="グリッターパープル">グリッターパープル</option>
      <option value="蛍光オレンジ">蛍光オレンジ</option>
      <option value="蛍光ピンク">蛍光ピンク</option>
      <option value="蛍光グリーン">蛍光グリーン</option>
      <option value="フルカラー(小)">フルカラー(小)</option>
      <option value="フルカラー(中)">フルカラー(中)</option>
      <option value="フルカラー(大)">フルカラー(大)</option>
    </select>

    <label>フォントNo.(その他):</label>
    <select name="font_no_other">
      <option value="">選択してください</option>
      <option value="E-01">E-01</option>
      <option value="E-02">E-02</option>
      <option value="E-03">E-03</option>
      <option value="E-05">E-05</option>
      <option value="E-06">E-06</option>
      <option value="E-09">E-09</option>
      <option value="E-10">E-10</option>
      <option value="E-13">E-13</option>
      <option value="E-14">E-14</option>
      <option value="E-15">E-15</option>
      <option value="E-16">E-16</option>
      <option value="E-17">E-17</option>
      <option value="E-18">E-18</option>
      <option value="E-19">E-19</option>
      <option value="E-20">E-20</option>
      <option value="E-21">E-21</option>
      <option value="E-22">E-22</option>
      <option value="E-23">E-23</option>
      <option value="E-24">E-24</option>
      <option value="E-25">E-25</option>
      <option value="E-26">E-26</option>
      <option value="E-27">E-27</option>
      <option value="E-28">E-28</option>
      <option value="E-29">E-29</option>
      <option value="E-30">E-30</option>
      <option value="E-31">E-31</option>
      <option value="E-32">E-32</option>
      <option value="E-33">E-33</option>
      <option value="E-34">E-34</option>
      <option value="E-35">E-35</option>
      <option value="E-37">E-37</option>
      <option value="E-38">E-38</option>
      <option value="E-40">E-40</option>
      <option value="E-41">E-41</option>
      <option value="E-42">E-42</option>
      <option value="E-43">E-43</option>
      <option value="E-44">E-44</option>
      <option value="E-45">E-45</option>
      <option value="E-46">E-46</option>
      <option value="E-47">E-47</option>
      <option value="E-50">E-50</option>
      <option value="E-51">E-51</option>
      <option value="E-52">E-52</option>
      <option value="E-53">E-53</option>
      <option value="E-54">E-54</option>
      <option value="E-55">E-55</option>
      <option value="E-56">E-56</option>
      <option value="E-57">E-57</option>
    </select>

    <label>デザインサンプル(その他):</label>
    <select name="design_sample_other">
      <option value="">選択してください</option>
      <option value="D-008">D-008</option>
      <option value="D-009">D-009</option>
      <option value="D-012">D-012</option>
      <option value="D-013">D-013</option>
      <option value="D-014">D-014</option>
      <option value="D-015">D-015</option>
      <option value="D-027">D-027</option>
      <option value="D-028">D-028</option>
      <option value="D-029">D-029</option>
      <option value="D-030">D-030</option>
      <option value="D-039">D-039</option>
      <option value="D-040">D-040</option>
      <option value="D-041">D-041</option>
      <option value="D-042">D-042</option>
      <option value="D-051">D-051</option>
      <option value="D-068">D-068</option>
      <option value="D-080">D-080</option>
      <option value="D-106">D-106</option>
      <option value="D-111">D-111</option>
      <option value="D-125">D-125</option>
      <option value="D-128">D-128</option>
      <option value="D-129">D-129</option>
      <option value="D-138">D-138</option>
      <option value="D-140">D-140</option>
      <option value="D-150">D-150</option>
      <option value="D-157">D-157</option>
      <option value="D-167">D-167</option>
      <option value="D-168">D-168</option>
      <option value="D-177">D-177</option>
      <option value="D-195">D-195</option>
      <option value="D-201">D-201</option>
      <option value="D-212">D-212</option>
      <option value="D-213">D-213</option>
      <option value="D-218">D-218</option>
      <option value="D-220">D-220</option>
      <option value="D-222">D-222</option>
      <option value="D-223">D-223</option>
      <option value="D-229">D-229</option>
      <option value="D-230">D-230</option>
      <option value="D-231">D-231</option>
      <option value="D-233">D-233</option>
      <option value="D-234">D-234</option>
      <option value="D-235">D-235</option>
      <option value="D-236">D-236</option>
      <option value="D-238">D-238</option>
      <option value="D-240">D-240</option>
      <option value="D-241">D-241</option>
      <option value="D-242">D-242</option>
      <option value="D-244">D-244</option>
      <option value="D-246">D-246</option>
      <option value="D-247">D-247</option>
      <option value="D-248">D-248</option>
      <option value="D-260">D-260</option>
      <option value="D-266">D-266</option>
      <option value="D-273">D-273</option>
      <option value="D-274">D-274</option>
      <option value="D-275">D-275</option>
      <option value="D-280">D-280</option>
      <option value="D-281">D-281</option>
      <option value="D-286">D-286</option>
      <option value="D-287">D-287</option>
      <option value="D-288">D-288</option>
      <option value="D-291">D-291</option>
      <option value="D-292">D-292</option>
      <option value="D-298">D-298</option>
      <option value="D-299">D-299</option>
      <option value="D-300">D-300</option>
      <option value="D-301">D-301</option>
      <option value="D-307">D-307</option>
      <option value="D-309">D-309</option>
      <option value="D-315">D-315</option>
      <option value="D-317">D-317</option>
      <option value="D-318">D-318</option>
      <option value="D-322">D-322</option>
      <option value="D-332">D-332</option>
      <option value="D-334">D-334</option>
      <option value="D-335">D-335</option>
      <option value="D-337">D-337</option>
      <option value="D-340">D-340</option>
      <option value="D-341">D-341</option>
      <option value="D-344">D-344</option>
      <option value="D-346">D-346</option>
      <option value="D-347">D-347</option>
      <option value="D-348">D-348</option>
      <option value="D-349">D-349</option>
      <option value="D-352">D-352</option>
      <option value="D-353">D-353</option>
      <option value="D-354">D-354</option>
      <option value="D-355">D-355</option>
      <option value="D-358">D-358</option>
      <option value="D-363">D-363</option>
      <option value="D-364">D-364</option>
      <option value="D-365">D-365</option>
      <option value="D-366">D-366</option>
      <option value="D-367">D-367</option>
      <option value="D-368">D-368</option>
      <option value="D-370">D-370</option>
      <option value="D-372">D-372</option>
      <option value="D-373">D-373</option>
      <option value="D-374">D-374</option>
      <option value="D-375">D-375</option>
      <option value="D-376">D-376</option>
      <option value="D-377">D-377</option>
      <option value="D-378">D-378</option>
      <option value="D-379">D-379</option>
      <option value="D-380">D-380</option>
      <option value="D-381">D-381</option>
      <option value="D-382">D-382</option>
      <option value="D-383">D-383</option>
      <option value="D-384">D-384</option>
      <option value="D-385">D-385</option>
      <option value="D-386">D-386</option>
      <option value="D-388">D-388</option>
      <option value="D-390">D-390</option>
      <option value="D-391">D-391</option>
      <option value="D-392">D-392</option>
      <option value="D-393">D-393</option>
      <option value="D-394">D-394</option>
      <option value="D-396">D-396</option>
      <option value="D-397">D-397</option>
      <option value="D-398">D-398</option>
      <option value="D-399">D-399</option>
      <option value="D-400">D-400</option>
      <option value="D-401">D-401</option>
      <option value="D-402">D-402</option>
      <option value="D-403">D-403</option>
      <option value="D-404">D-404</option>
      <option value="D-405">D-405</option>
    </select>
    </select>

    <label>カスタムプリントデータ(その他):</label>
    <input type="file" name="position_data_other">
    </div>

    <!-- ▼▼ プリント位置(その他) => 選択式に変更 ▼▼ -->
    <label>プリント位置(その他):</label>
    <select name="other_positions_selected">
      <option value="">選択してください</option>
      <option value="左袖：袖口">左袖：袖口</option>
      <option value="左袖：長袖中央">左袖：長袖中央</option>
      <option value="左袖：長袖肩口">左袖：長袖肩口</option>
      <option value="左袖：長袖袖口">左袖：長袖袖口</option>
      <option value="右袖：袖口">右袖：袖口</option>
      <option value="右袖：長袖中央">右袖：長袖中央</option>
      <option value="右袖：長袖肩口">右袖：長袖肩口</option>
      <option value="右袖：長袖袖口">右袖：長袖袖口</option>
    </select>


    <h3>背ネーム・背番号プリント</h3>
    <p class="instruction">※複数選択可能</p>
    <div class="checkbox-group">
      <label><input type="checkbox" name="back_name_number_print[]" value="ネーム&背番号セット"> ネーム&背番号セット</label>
      <label><input type="checkbox" name="back_name_number_print[]" value="ネーム(大)"> ネーム(大)</label>
      <label><input type="checkbox" name="back_name_number_print[]" value="ネーム(小)"> ネーム(小)</label>
      <label><input type="checkbox" name="back_name_number_print[]" value="番号(大)"> 番号(大)</label>
      <label><input type="checkbox" name="back_name_number_print[]" value="番号(小)"> 番号(小)</label>
      <label><input type="checkbox" name="back_name_number_print[]" value="ネーム＆背番号を使わない"> ネーム＆背番号を使わない</label>
    </div>

    <!-- ▼▼ 背ネーム・背番号のカラー設定 ▼▼ -->
    <h3>背ネーム・背番号 カラー設定</h3>
    <p>「単色」または「フチ付き(2色)」を選択してください。</p>

    <!-- ラジオボタン：単色 or フチ付き -->
    <div class="radio-group" id="nameNumberColorType">
      <label>
        <input type="radio" name="name_number_color_type" value="single" checked>
        単色
      </label>
      <label>
        <input type="radio" name="name_number_color_type" value="outline">
        フチ付き(2色)
      </label>
    </div>

    <!-- ▼ 単色カラー ▼ -->
    <div id="singleColorSection">
      <label>単色カラー:</label>
      <select name="single_color_choice">
        <option value="">選択してください</option>
        <option value="ホワイト">ホワイト</option>
        <option value="グレー">グレー</option>
        <option value="ネイビー">ネイビー</option>
        <option value="ブラック">ブラック</option>
        <option value="ライトブルー">ライトブルー</option>
        <option value="ブルー">ブルー</option>
        <option value="イエロー">イエロー</option>
        <option value="オレンジ">オレンジ</option>
        <option value="ピンク">ピンク</option>
        <option value="ホットピンク">ホットピンク</option>
        <option value="レッド">レッド</option>
        <option value="パープル">パープル</option>
        <option value="ライトグリーン">ライトグリーン</option>
        <option value="グリーン">グリーン</option>
        <option value="シルバー">シルバー</option>
        <option value="ゴールド">ゴールド</option>
        <option value="グリッターシルバー">グリッターシルバー</option>
        <option value="グリッターゴールド">グリッターゴールド</option>
        <option value="グリッターピンク">グリッターピンク</option>
      </select>
    </div>

    <!-- ▼ フチ付き(2色) ▼ -->
    <div id="outlineColorSection" style="display: none; margin-top:16px;">
      <label>タイプ (フチ付きデザイン):</label>
      <select name="outline_type">
        <option value="">選択してください</option>
        <option value="FT-01">FT-01</option>
        <option value="FT-02">FT-02</option>
      </select>

      <label>文字色:</label>
      <select name="outline_text_color">
        <option value="">選択してください</option>
        <option value="ホワイト">ホワイト</option>
        <option value="グレー">グレー</option>
        <option value="ネイビー">ネイビー</option>
        <option value="ブラック">ブラック</option>
        <option value="ライトブルー">ライトブルー</option>
        <option value="ブルー">ブルー</option>
        <option value="イエロー">イエロー</option>
        <option value="オレンジ">オレンジ</option>
        <option value="ピンク">ピンク</option>
        <option value="ホットピンク">ホットピンク</option>
        <option value="レッド">レッド</option>
        <option value="パープル">パープル</option>
        <option value="ライトグリーン">ライトグリーン</option>
        <option value="グリーン">グリーン</option>
        <option value="シルバー">シルバー</option>
        <option value="ゴールド">ゴールド</option>
        <option value="グリッターシルバー">グリッターシルバー</option>
        <option value="グリッターゴールド">グリッターゴールド</option>
        <option value="グリッターピンク">グリッターピンク</option>
      </select>

      <label>フチ色:</label>
      <select name="outline_edge_color">
        <option value="">選択してください</option>
        <option value="ホワイト">ホワイト</option>
        <option value="グレー">グレー</option>
        <option value="ネイビー">ネイビー</option>
        <option value="ブラック">ブラック</option>
        <option value="ライトブルー">ライトブルー</option>
        <option value="ブルー">ブルー</option>
        <option value="イエロー">イエロー</option>
        <option value="オレンジ">オレンジ</option>
        <option value="ピンク">ピンク</option>
        <option value="ホットピンク">ホットピンク</option>
        <option value="レッド">レッド</option>
        <option value="パープル">パープル</option>
        <option value="ライトグリーン">ライトグリーン</option>
        <option value="グリーン">グリーン</option>
        <option value="シルバー">シルバー</option>
        <option value="ゴールド">ゴールド</option>
        <option value="グリッターシルバー">グリッターシルバー</option>
        <option value="グリッターゴールド">グリッターゴールド</option>
        <option value="グリッターピンク">グリッターピンク</option>
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